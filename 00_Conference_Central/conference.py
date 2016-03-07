#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime
import time

import logging
import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.ext import ndb
from google.appengine.api import memcache, taskqueue


from models import StringMessages
from models import StringMessage
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import TeeShirtSize
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import Session
from models import CreateSessionForm
from models import SessionForm
from models import SessionForms
from models import SessionsOfConferenceByType
from models import QuerySessionsByDurationForm
from models import StartTime
from models import FeaturedSpeakerForm
from models import SpeakerForm
from models import HighlightsForm
from models import Speaker
from models import QuerySpeakerForm
from models import SpeakerForms
from models import NewSpeakerForm

from utils import getUserId

from models import Conference
from models import ConferenceForm

from settings import WEB_CLIENT_ID

from models import BooleanMessage
from models import ConflictException


CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SESS_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1),
)

SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerKey=messages.StringField(1),
)

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED_SPEAKER"

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

SESSION_DEFAULTS = {
    "typeOfSession": [ "Default", "Type" ],
    "startTime": "08:00",
    "highlights": [ "Default", "Highlight" ],
    "duration": 1,
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

@endpoints.api( name='conference',
                version='v1',
                allowed_client_ids=[WEB_CLIENT_ID, endpoints.API_EXPLORER_CLIENT_ID],
                scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name,
                        getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if
        non-existent."""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # TODO 1
        # step 1. copy utils.py from additions folder to this folder
        #         and import getUserId from it
        # step 2. get user id by calling getUserId(user)
        user_id = getUserId(user)
        # step 3. create a new key of kind Profile from the id
        p_key = ndb.Key(Profile, user_id)

        # TODO 3
        # get the entity from datastore by using get() on the key
        profile = p_key.get()
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            # TODO 2
            # save the profile to datastore
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
            # TODO 4
            # put the modified profile to datastore
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""

        # If no input provided return none.
        if not conf:
            return

        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning
        ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException(
                "Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
            for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model and outbound
        # Message.
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on
        # start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(
                data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(
                data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        # both for data model and outbound Message
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
            setattr(request, "seatsAvailable", data["maxAttendees"])

        # make Profile Key from user ID
        p_key = ndb.Key(Profile, user_id)
        # allocate new Conference ID with Profile key as parent
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        # make Conference key from ID
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference and return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': request},
            url='/tasks/send_confirmation_email')

        return request


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        "Make modifications to the users proflie."
        return self._doProfile(request)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

         # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") \
            for conf in conferences])


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST',
            name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id =  getUserId(user)
        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, getattr(prof, 'displayName')) for conf in confs])


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(
                filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name)
                for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous
                # filters disallow the filter if inequality was performed on a
                # different field before track the field on which the
                # inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='filterPlayground',
            http_method='POST',
            name='filterPlayground')
    def filterPlayground(self, request):
        """Queries all conferences in LOndon with 'Medical Innovations' as the
        topic and a maximum attendance greater than ten."""
        q = Conference.query()
        q = q.filter(Conference.city == 'London')
        q = q.filter(Conference.topics == 'Medical Innovations')
        q = q.order(Conference.name)
        q = q.filter(Conference.maxAttendees > 10)
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "")
            for conf in q])


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        # TODO:
        # step 1: get user profile
        prof = self._getProfileFromUser()
        # step 2: get conferenceKeysToAttend from profile.
        conf_keys = [ndb.Key(urlsafe=wsck)\
         for wsck in prof.conferenceKeysToAttend]
        # to make a ndb key from websafe key you can use:
        # step 3: fetch conferences from datastore.
        conferences = ndb.get_multi(conf_keys)

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, "")\
         for conf in conferences])

# - - - Sessions - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _addFeaturedSpeaker(url_conf_key, url_speaker_key):
        """Checks if the speaker speaking at conference's session is speaking at
        the most sessions at that conference."""

        # Get all sssions of the given conferene and filter given speaker.
        q = Session.query(ancestor=ndb.Key(urlsafe=url_conf_key))

        speaker = ndb.Key(urlsafe=url_speaker_key).get()
        sessions = q.filter(Session.speaker == speaker)

        # if there is more than one session by the same speaker add the
        # speaker and thier sesssions to memcache.
        session_num = sessions.count()

        # return if the speaker is only giving one session at the conference.
        if session_num <= 1:
            return

        # check if the speaker is doing more sessions than any other at the
        # conference.
        cached_speaker = memcache.get(url_conf_key)
        if cached_speaker:
            most_sessions = len(cached_speaker['websafeSessionKeys'])
            if session_num <= most_sessions:
                return

        # set the speaker as featured if they are doing the most sessions.
        featured_speaker = {'speaker': speaker.key.urlsafe(),
                            'websafeSessionKeys': [session.key.urlsafe() for session in sessions],}
        memcache.set(url_conf_key, featured_speaker)


    @endpoints.method(CONF_GET_REQUEST, FeaturedSpeakerForm,
            http_method='GET', path='featuredspeaker',
            name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Takes the websafeKey of a conference and returns a featured
        speaker form object."""
        featured_speaker = memcache.get(request.websafeConferenceKey)

        if not featured_speaker:
            raise endpoints.NotFoundException("""No featured speaker found in
            memcache for the given conference.""")
        return FeaturedSpeakerForm(speaker=featured_speaker['speaker'],
            websafeSessionKeys=featured_speaker['websafeSessionKeys'])


    def _createSessionObject(self, request):
        """Create a Session object by copying the data from a SessionForm
        object"""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required.')
        user_id = getUserId(user)

        if not request.websafeConferenceKey:
            raise endpoints.BadRequestException(
                'websafeConfernceKey must be provided.')

        # verify that websafeSpeaker key was provided and points to a speaker
        if not request.websafeSpeakerKey:
            raise endpoints.BadRequestException(
                'websafeSpeakerKey must be provided.')
        speaker_obj = ndb.Key(urlsafe=request.websafeSpeakerKey).get()

        if not speaker_obj:
            raise endpoints.NotFoundException(
                'Speaker not found.')

        conf_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        # verify that the key is for a Conference object.
        if conf_key.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'The websafeKey must point to a Conference entity.')
        conf = conf_key.get()

        if not conf:
            raise endpoints.NotFoundException(
                'Conference not found.')

        if user_id != conf.organizerUserId:
            raise endpoints.UnauthorizedException(
                'Only conference organizer may create sessions for a'
                ' conference.')

        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeConferenceKey']
        del data['websafeSpeakerKey']

        # set default values to empty fields for both data model and inbound
        # request.
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]
                setattr(request, df, SESSION_DEFAULTS[df])

        # put dates and times into datetime formats in data model
        if data['date']:
            data['date'] = datetime.strptime(
                data['date'][:10], '%Y-%m-%d').date()
        if data['startTime']:
            time_obj = datetime.strptime(
                data['startTime'][:5], '%H:%M').time()
            data['startTime'] = StartTime(hour=time_obj.hour,
                                          minute=time_obj.minute)

        c_id = Session.allocate_ids(size=1, parent=conf_key)[0]
        c_key = ndb.Key(Session, c_id, parent=conf_key)
        data['key'] = c_key
        data['speaker'] = speaker_obj

        new_session = Session(**data)
        new_session.put()

        # Update the featured speaker if there is one.
        self._addFeaturedSpeaker(
            request.websafeConferenceKey, request.websafeSpeakerKey)

        # Check to see if the added speaker has the most sessions at the
        # given conference.
        taskqueue.add(params={'speaker': request.websafeSpeakerKey,
                              'conf_key': conf_key.urlsafe()},
                      url='/tasks/add_featured_speaker')

        # return a SessionForm object with the newly created sessions data.

        return self._copySessionToForm(new_session)


    @endpoints.method(CreateSessionForm, SessionForm,
                      path='session', http_method='POST', name='createSession')
    def createSession(self, request):
        """Open only to the organizer of the conference."""
        return self._createSessionObject(request)


    def _copySessionToForm(self, sess):
        """Copy relevant fields from Session to SessionForm."""

        # If no input provided return none.
        if not sess:
            return

        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(sess, field.name):
                # convert Date to date string; just copy others
                if field.name == 'date' or field.name == 'startTime':
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                elif field.name == 'speaker':
                    setattr(sf, field.name, getattr(sess, field.name).speaker)
                else:
                    setattr(sf, field.name, getattr(sess, field.name))
            elif field.name == "websafeSessionKey":
                setattr(sf, field.name, sess.key.urlsafe())
        sf.check_initialized()
        return sf


    @endpoints.method(CONF_GET_REQUEST, SessionForms,
            path='sessions/byconference',
            http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Given a conference, return all sessions"""
        conf_key = ndb.Key(urlsafe=request.websafeConferenceKey)

        # verify websafekey points to Conference entity.
        if conf_key.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'websafeKey must point to Conference entity.')
        sessions = Session.query(ancestor=conf_key)
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions])


    @endpoints.method(SPEAKER_GET_REQUEST, SessionForms,
            path='sessions/byspeaker',
            http_method='GET',
            name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Given a speaker websafe key , return all sessions given by this particular
        speaker, across all conferences"""
        speaker_obj = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        q = Session.query().filter(Session.speaker == speaker_obj)
        return SessionForms(
            items=[self._copySessionToForm(sess) for sess in q])


    @endpoints.method(SessionsOfConferenceByType, SessionForms,
            path='sessions/bytype',
            http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Given a conference, return all sessions of a specified type
        (eg lecture, keynote, workshop)"""

        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException(
                'You must be logged in to call this method.')
        user_id = getUserId(user)

        conf_key = ndb.Key(
            urlsafe=request.websafeConferenceKey)

        # verify websafekey points to Conference entity.
        if conf_key.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'websafeKey must point to Conference entity.')
        sessions = Session.query(ancestor=conf_key)

        q = Session.query(
            ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        q = q.filter(request.type == Session.typeOfSession)

        return SessionForms(
            items=[self._copySessionToForm(sess) for sess in q])


    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='sessions/beforeseven',
            http_method='GET', name='beforeSevenNonWorkshopSession')
    def beforeSevenNonWorkshopSession(self, request):
        """Returns all sessions before 7PM that are not workshops."""
        q = Session.query()
        q = q.filter(Session.startTime.hour.IN([h for h in range(19)]))
        q = q.filter(Session.typeOfSession != 'Workshop')

        return SessionForms(
            items=[self._copySessionToForm(session) for session in q])


    @endpoints.method(HighlightsForm, SessionForms,
            path='sessions/byhighlights',
            http_method='GET', name='getSessionsByHighlights')
    def getSessionsByHighlights(self, request):
        """Returns all sessions with any of the highlights provided"""
        q = Session.query()
        q = q.filter(Session.highlights.IN(request.highlights))

        return SessionForms(
            items=[self._copySessionToForm(session) for session in q])


    @endpoints.method(QuerySessionsByDurationForm, SessionForms,
            path='sessions/byduration',
            http_method='GET', name='getSessionsByDuration')
    def getSessionsByDurartion(self, request):
        """Returns all sessions with a duration less than or equal to the
        integer provided."""
        q = Session.query()
        q = q.filter(Session.duration <= request.duration)

        return SessionForms(
            items=[self._copySessionToForm(session) for session in q])


# - - - Speaker - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(NewSpeakerForm, SpeakerForm,
            path='speaker/create',
            http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """Create a new spaeker form with provided speaker name and
        organization"""

        # make sure user is logged in.
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # copy request data into a dictionary.
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # get a key for the speaker.
        speaker_id = Speaker.allocate_ids(size=1)[0]
        speaker_key = ndb.Key(Speaker, speaker_id)
        data['key'] = speaker_key

        new_speaker = Speaker(**data)
        new_speaker.put()

        return self._copySpeakerToForm(new_speaker)


    def _copySpeakerToForm(self, speaker):
        """Copy data from a Speaker entity to a SpeakerForm"""

        # If no input provided return none.
        if not speaker:
            return


        speaker_form = SpeakerForm()
        for field in speaker_form.all_fields():
            if hasattr(speaker, field.name):
                setattr(speaker_form, field.name, getattr(speaker, field.name))
            elif field.name == "websafeSpeakerKey":
                setattr(speaker_form, field.name, speaker.key.urlsafe())
        speaker_form.check_initialized()

        return speaker_form


    @endpoints.method(SPEAKER_GET_REQUEST, SpeakerForm,
            http_method='GET',
            path='speaker/getbywsk', name='getSpeakerByWsk')
    def getSpeakerByWsk(self, request):
        """Get the Speaker for a given websafeSpeakerKey."""
        speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        return self._copySpeakerToForm(speaker)


    @endpoints.method(QuerySpeakerForm, SpeakerForms,
            http_method='GET',
            path='queryspeaker', name='querySpeaker')
    def querySpeaker(self, request):
        """Queries all speakers with the name and or organization provided."""

        q = Speaker.query()
        q = q.filter(Speaker.speaker == request.speaker)

        # if an organization query is provided, query speaker by organization
        if request.organization:
            q = q.filter(Speaker.organization == request.organization)

        return SpeakerForms(items = [self._copySpeakerToForm(s) for s in q])



# - - - Wishlist - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(SESS_GET_REQUEST, ProfileForm,
            http_method='POST',
            path='wisthlist/add', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Adds the session to the user's list of sessions they are
        interested in attending"""
        # verify that the weafekey points to a session entity.
        s_key = ndb.Key(urlsafe=request.websafeSessionKey)
        if s_key.kind() != 'Session':
            raise endpoints.BadRequestException(
                'websafeKey must point to a Session entity.')

        # check to see if session exists.
        session = s_key.get()
        if not session:
            raise endpoints.NotFoundException('Session not found.')

        user = endpoints.get_current_user()

        if not user:
            raise endpoints.UnauthorizedException('Authorization required.')
        user_id = getUserId(user)

        prof = ndb.Key(Profile, user_id).get()

        # Check is session is already on the wishlist.
        if request.websafeSessionKey in prof.wishList:
            raise ConflictException(
                'The session is already on your wishlist.')
        prof.wishList.append(request.websafeSessionKey)
        prof.put()

        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='wishlist/getusers',
            http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Query for all the sessions in a conference that the user is
        interested in."""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException(
                'You must be logged in to use this method.')

        user_id = getUserId(user)
        prof = ndb.Key(Profile, user_id).get()
        if not prof:
            raise endpoints.NotFoundException('Profile not found.')
        wishlist = prof.wishList
        wishlist_keys = [ndb.Key(urlsafe=wish) for wish in wishlist]
        wishlist_sessions = ndb.get_multi(wishlist_keys)
        return SessionForms(
            items=[self._copySessionToForm(wish) for wish in wishlist_sessions])


    @endpoints.method(SESS_GET_REQUEST, ProfileForm,
            path='wishlist/delete',
            http_method='POST', name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        """Removes the session from the user's list of sessions they are
        interested in attending."""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException(
                'You must be logged in to use this method.')

        user_id = getUserId(user)

        prof = ndb.Key(Profile, user_id).get()
        # verify that the session is in the user's wishlist.
        if request.websafeSessionKey not in prof.wishList:
            raise endpoints.NotFoundException('Session not on wishlist.')

        prof.wishList.remove(request.websafeSessionKey)
        prof.put()

        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            http_method='GET',
            path='wishlist/unregistered', name='getNotRegisteredWishlist')
    def getNotRegisteredWishlist(self, request):
        """Returns all sesssions on a users wishlist where the user is not
        registered for the conference."""
        prof = self._getProfileFromUser()
        wishlist = prof.wishList
        wishlist_keys = [ndb.Key(urlsafe=wish) for wish in wishlist]

        # Get conferences attending.
        attending_wsk = prof.conferenceKeysToAttend
        attending_keys = [ndb.Key(urlsafe=wsk) for wsk in attending_wsk]

        # Get the parent conferenes of all sessions in the query.
        conf_keys = [session_key.parent() for session_key in wishlist_keys]

        # Query confreences with wishlist session as child.
        q = Conference.query()
        q = q.filter(Conference.key.IN([key for key in conf_keys]))

        # Query conferences that do not include those being attended.
        for key in attending_keys:
            q = q.filter(Conference.key != key)

        return ConferenceForms(
            items=[self._copyConferenceToForm(conference, "")
                for conference in q])

# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore and return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement and assign to memcache; used by
        memcache cron job and putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = '%s %s' % (
                'Last chance to attend! The following conferences '
                'are nearly sold out:',
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        # TODO 1
        # return an existing announcement from Memcache or an empty string
        announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
        if not announcement:
            announcement = ""
        return StringMessage(data=announcement)


# registers API
api = endpoints.api_server([ConferenceApi])
