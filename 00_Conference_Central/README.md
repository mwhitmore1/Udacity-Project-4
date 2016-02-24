App Engine application for the Udacity training course.

## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
2. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
3. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
4. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
5. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting
   your local server's address (by default [localhost:8080][5].)
6. Generate your client library(ies) with [the endpoints tool][6].
7. Deploy your application.
8. Go to https://apis-explorer.appspot.com/apis-explorer/?base=https:// [ insert your app ID here ] .appspot.com/_ah/api#p/, to access the google API endpoints for the application.  

Sessions and Speakers

Sessions are aspects of a conference.  When a session is created via the createSession() method, the user is required to provide the websafe ID of the parent conference in the 'websafeConferenceKey' field.  The websafe ID for the parent conference is also required to use the getConferenceSessions and the getConferenceSessions by type methods to specify which conference is to be the target of the query.  

Each session has a speaker.  The speaker is saved as a string.  When a speaker is speaking at two or more sessions at a conference, that speaker is eligible to be the 'featured speaker' of that conference.  Any time a session entity is created vai the createSession() method, the addFeaturedSpeaker() endpoint method will be called.  The addFeaturedSpeaker() method checks to see if the speaker is speaking at at least two sessions of the conference, and if so, how whether that speaker is speaking at more sessions at that conference than any other speaker.  If the speaker is speaking at the most sessions for the given conference, he/she will be considered the 'featured speaker.'  The 'featured speaker' will be stored in memcache along with SessionForm entities for all sessions the 'featured speaker' will be speaking at.  This memcached 'featured speaker' data may be obtained with the getFeaturedSpeaker() endpoint method.   

Querying for no workshops

For those uninterested in session having workshops or sessions held later than 7, the beforeSevenNonWorkshop() endpoint method has been added.  This method overcomes NDB's prohibition on multiple inequality filters by implementing a for loop to create a list of all hours in a day prior to 7PM.  The startTime property is a structured property.  Its component properties,  'hour' and 'minute', are both integer properties.  Thus, the list of integers created by the beforeSevenNonWorkshop() method can be used to query all sessions before 7PM.  

Additional Query Types

Two additional query types have been added to enable the user to query session entities: getSessionsByHighlights and get SessionsByDuration.  

The getSessionsByHighlights() method provides the user with the ability to search for a sessions based on the session's highlights.  The getSessionsByHighlights() method takes a list of highlights, which are entered as strings and returns a SessionForms entity containing any session entity that has at least one of the highlights listed in the input.  

The getSessionsByDuration() method takes as input an integer representing the maximum desired duration, and returns a SessionForms entity containing all sessions with a duration less than or equal to the duration input.  