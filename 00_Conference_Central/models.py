#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb


class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)
    wishList = ndb.StringProperty(repeated=True)


class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)


class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)
    wishList = messages.StringField(4, repeated=True)


class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15


class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty()
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()


class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6)
    month           = messages.IntegerField(7, variant=messages.Variant.INT32)
    maxAttendees    = messages.IntegerField(8, variant=messages.Variant.INT32)
    seatsAvailable  = messages.IntegerField(9, variant=messages.Variant.INT32)
    endDate         = messages.StringField(10)
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)


class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)


class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)


class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)


class StartTime(ndb.Model):
    """StartTime == used for the startTime property of the Conference class
    to make the start time of allow greater/less than queries of a conferences
    start times."""
    hour  = ndb.IntegerProperty()
    minute = ndb.IntegerProperty()


class Session(ndb.Model):
    name = ndb.StringProperty()
    highlights = ndb.StringProperty(repeated=True)
    speaker = ndb.StringProperty()
    duration = ndb.IntegerProperty()
    typeOfSession = ndb.StringProperty(repeated=True)
    date = ndb.DateProperty()
    startTime = ndb.StructuredProperty(StartTime)


class CreateSessionForm(messages.Message):
    """CreateSessionForm -- used to send data to server to create new session
    object."""
    name = messages.StringField(1)
    date = messages.StringField(2)
    startTime = messages.StringField(3)
    highlights = messages.StringField(4, repeated=True)
    speaker = messages.StringField(5)
    duration = messages.IntegerField(6)
    typeOfSession = messages.StringField(7, repeated=True)
    websafeConferenceKey = messages.StringField(8)


class SessionForm(messages.Message):
    """SessionForm -- outbound message used to pass data about a session."""
    name = messages.StringField(1)
    date = messages.StringField(2)
    startTime = messages.StringField(3)
    highlights = messages.StringField(4, repeated=True)
    speaker = messages.StringField(5)
    duration = messages.IntegerField(6)
    typeOfSession = messages.StringField(7, repeated=True)
    websafeSessionKey = messages.StringField(8)


class SessionForms(messages.Message):
    """SessionForms -- multiple Session outbound form message"""
    items = messages.MessageField(SessionForm, 1, repeated=True)


class QuerySessionsByDurationForm(messages.Message):
    """QuerySessionByDurationForm -- Session query inbound form message.
    Takes an integer."""
    duration = messages.IntegerField(1)


class SessionsOfConferenceByType(messages.Message):
    """Returns all sessions of a given conference with a given topic"""
    type = messages.StringField(1)
    websafeConferenceKey = messages.StringField(2)


class FeaturedSpeakerForm(messages.Message):
    speaker = messages.StringField(1)
    sessions = messages.MessageField(SessionForms, 2)


# needed for conference registration
class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)


class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


class SpeakerForm(messages.Message):
    """SpeakerForm -- outbound (single) string message"""
    speaker = messages.StringField(1, required=True)


class HighlightsForm(messages.Message):
    """HighlightsForm -- outbound (multiple) string message."""
    highlights = messages.StringField(1, repeated=True)


# needed for memcache

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)


class StringMessages(messages.Message):
    """"StringMessages-- outbound (multi) string message"""
    data = messages.StringField(1, repeated=True)


