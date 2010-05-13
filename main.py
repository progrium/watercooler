from google.appengine.ext import webapp, db
from google.appengine.api import urlfetch, memcache, users
from google.appengine.ext.webapp import util, template
from google.appengine.api.labs import taskqueue
from django.utils import simplejson
import urllib
import base64

# Make sure you make a keys.py file with these
from keys import ACCOUNTSID, AUTHTOKEN, REALTIME_SERVER

def pub(path='/', payload=None):
    return urlfetch.fetch('https://%s/watercooler%s' % (REALTIME_SERVER, path), 
        method='POST', 
        headers={"Authorization": "Basic "+base64.b64encode('%s:%s' % (ACCOUNTSID, AUTHTOKEN))},
        payload=urllib.urlencode(payload))

class Room(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    #name = db.StringProperty(required=True)
    participants = db.StringListProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    
    def id(self):
        return self.key().id()
    
    def join(self, user):
        nick = user.nickname()
        if nick not in self.participants:
            self.participants.append(nick)
            self.put()
            message = Message(body="%s has entered the room" % nick, type='JoinMessage', room=self)
            message.put()
            message.broadcast()
        
    def leave(self, user):
        nick = user.nickname()
        if nick in self.participants:
            self.participants.remove(nick)
            self.put()
            message = Message(body="%s has left the room" % nick, type='LeaveMessage', room=self)
            message.put()
            message.broadcast()
    

class Message(db.Model):
    room = db.ReferenceProperty(Room)
    user = db.UserProperty(auto_current_user_add=True)
    body = db.StringProperty(required=True)
    type = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    
    
    def broadcast(self):
        pub('/room/%s/live.json' % self.room.id(), {
            'type':self.type, 
            'body':self.body, 
            'user':self.user.nickname() if self.user else ''})
    


class RoomHandler(webapp.RequestHandler):
    @util.login_required
    def get(self, room_id):
        room = Room.get_by_id(int(room_id))
        if room:
            user = users.get_current_user()
            logout_url = users.create_logout_url('/')
            room = Room.get_by_id(int(room_id))
            room.join(user)
            participants = map(lambda p: (p.replace('@', '.').replace('.', '-'),p), room.participants)
            realtime_server = REALTIME_SERVER
            self.response.out.write(template.render('templates/room.html', locals()))

class SpeakHandler(webapp.RequestHandler):
    def post(self, room_id):
        room = Room.get_by_id(int(room_id))
        if room:
            message = Message(body=self.request.get('body'), type='TextMessage', room=room, user=users.get_current_user())
            message.put()
            message.broadcast()
            self.response.out.write("OK")

class LeaveHandler(webapp.RequestHandler):
    def post(self, room_id):
        room = Room.get_by_id(int(room_id))
        if room:
            room.leave(users.get_current_user())
            self.response.out.write("OK")

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        self.response.out.write(template.render('templates/main.html', locals()))
    
    def post(self):
        room = Room()
        room.put()
        self.redirect('/room/%s' % room.id())

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/room/(\d+)', RoomHandler),
        ('/room/(\d+)/speak', SpeakHandler),
        ('/room/(\d+)/leave', LeaveHandler),
      ], debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()