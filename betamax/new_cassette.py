from betamax.cassette import (Interaction, timestamp,
                              serialize_prepared_request,
                              serialize_response)
from betamax.matchers import matcher_registry
from betamax.serializers import serializer_registry, SerializerProxy
from datetime import datetime
from functools import partial


class NewCassette(object):

    default_cassette_options = {
        'record_mode': 'once',
        'match_requests_on': ['method', 'uri'],
        're_record_interval': None,
        'placeholders': []
    }

    def __init__(self, cassette_name, serialization_format, **kwargs):
        #: Short name of the cassette
        self.cassette_name = cassette_name

        self.serialized = None

        # Determine the record mode
        self.record_mode = kwargs.get(
            'record_mode',
            NewCassette.default_cassette_options['record_mode']
            )

        # Retrieve the serializer for this cassette
        serializer = serializer_registry.get(serialization_format)
        if serializer is None:
            raise ValueError(
                'No serializer registered for {0}'.format(serialization_format)
                )

        self.serializer = SerializerProxy(serializer, cassette_name,
                                          self.is_recording())

        # Determine which placeholders to use
        self.placeholders = kwargs.get(
            'placeholders',
            NewCassette.default_cassette_options['placeholders']
            )

        # Initialize the interactions
        self.interactions = []

        # Initialize the match options
        self.match_options = set()

        self.load_interactions()

    def clear(self):
        # Clear out the interactions
        self.interactions = []
        # Serialize to the cassette file
        self._save_cassette()

    @property
    def earliest_recorded_date(self):
        """The earliest date of all of the interactions this cassette."""
        if self.interactions:
            i = sorted(self.interactions, key=lambda i: i.recorded_at)[0]
            return i.recorded_at
        return datetime.now()

    def eject(self):
        self._save_cassette()

    def find_match(self, request):
        """Find a matching interaction based on the matchers and request.

        This uses all of the matchers selected via configuration or
        ``use_cassette`` and passes in the request currently in progress.

        :param request: ``requests.PreparedRequest``
        :returns: :class:`Interaction <Interaction>`
        """
        opts = self.match_options
        # Curry those matchers
        matchers = [partial(matcher_registry[o].match, request) for o in opts]

        for i in self.interactions:
            if i.match(matchers):  # If the interaction matches everything
                if self.record_mode == 'all':
                    # If we're recording everything and there's a matching
                    # interaction we want to overwrite it, so we remove it.
                    self.interactions.remove(i)
                    break
                return i

        # No matches. So sad.
        return None

    def is_empty(self):
        """Determines if the cassette when loaded was empty."""
        return not self.serialized

    def is_recording(self):
        """Returns if the cassette is recording."""
        values = {
            'none': False,
            'once': self.is_empty(),
        }
        return values.get(self.record_mode, True)

    def load_interactions(self):
        if self.serialized is None:
            self.serialized = self.serializer.deserialize()

        interactions = self.serialized.get('http_interactions', [])
        self.interactions = [Interaction(i) for i in interactions]

        for i in self.interactions:
            i.replace_all(self.placeholders, ('placeholder', 'replace'))

    def sanitize_interactions(self):
        for i in self.interactions:
            i.replace_all(self.placeholders)

    def serialize_interaction(self, response, request):
        return {
            'request': serialize_prepared_request(request,
                                                  self.serialize_format),
            'response': serialize_response(response, self.serialize_format),
            'recorded_at': timestamp(),
        }

    # Private methods
    def _save_cassette(self):
        self.sanitize_interactions()

        cassette_data = {
            'http_interactions': [i.json for i in self.interactions],
            'recorded_with': 'betamax/{version}'
        }
        self.serializer.serialize(cassette_data)
