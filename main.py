#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, string, re
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
import urllib, hashlib
import logging

# Wedle konwencji pythonowej stringi w 3 cudzysłowach jako pierwsze w klasie/funkcji służą jako dokumentacja
def gravatar(email, size=24):
  """zwraca url obrazka"""
  return "http://www.gravatar.com/avatar.php?" + urllib.urlencode({'gravatar_id':hashlib.md5(email.lower()).hexdigest(), 'default':'monsterid', 'size':str(size)})

def is_email(email):
  """is_email('nie$email@gmail.com') #=> False"""
  return re.match('^([^@\s]+)@((?:[-a-z0-9]+\.)+[a-z]{2,})$', email)

def parse_date(date):
  return date.strftime("dnia %d.%m.%y o %H:%M")

def to_genitive(word, is_male):
  """to_genitive('kraxi', True) #=> 'kraxiego'"""
  text = word.strip()
  if is_email(text): return text
  if text.upper() == "JA": return "mnie"
  r = re.match('^(.+)i$', text, re.I)
  if r: return r.group(1) + 'iego' if is_male else text
  r = re.match('^(.+)y$', text, re.I)
  if r and is_male: return r.group(1) + 'ego'
  r = re.match('^(.+)ciek$', text, re.I)
  if r: return r.group(1) + u'ćka'
  r = re.match('^(.+)siek$', text, re.I)
  if r: return r.group(1) + u'śka'
  r = re.match('^(.+)ziek$', text, re.I)
  if r: return r.group(1) + u'źka'
  r = re.match('^(.+)ek$', text, re.I)
  if r: return r.group(1) + 'ka'
  r = re.match('^(.+)(k|l)a$', text, re.I)
  if r: return r.group(1) + r.group(2) + 'i'
  r = re.match('^(.+)a$', text, re.I)
  if r: return r.group(1) + 'y'
  r = re.match('^(.+)e$', text, re.I)
  if r: return text
  r = re.match(u'^(.+)ś$', text, re.I)
  if r: return r.group(1) + 'sia' if is_male else text
  r = re.match('^(.+)cieq$', text, re.I)
  if r: return r.group(1) + u'ćqa' if is_male else text
  r = re.match('^(.+)eq$', text, re.I)
  if r: return r.group(1) + 'qa' if is_male else text
  r = re.match('^(.+)q$', text, re.I)
  if r: return r.group(1) + 'ka' if is_male else text
  r = re.match('^(.+)au$', text, re.I)
  if r: return r.group(1) + 'aua'
  r = re.match('^(.+)eu$', text, re.I)
  if r: return r.group(1) + 'ua'
  r = re.match('^(.+)o$', text, re.I)
  if r: return r.group(1) + 'a'
  r = re.match('^(.+)u$', text, re.I)
  if r: return r.group(1) + 'a'
  return text + "a"

class Hash(object):
  """Klasa nadająca hashowi naturę obiektu (efekt jak w js).
  Potrzebna do przekazywania skomplikowanych struktur danych do template'ów.
  
  hash = Hash({'a': 'A'})
  hash.a #=> 'A'"""
  _data = {}
  def __init__(self, hash):
    self.__dict__['_data'] = hash
  def __getattr__(self, name):
    return self.__dict__['_data'][name]
  def __setattr__(self, name, val):
    self.__dict__['_data'][name] = val

class User(db.Model):
  """Zarejestrowana osoba.
  Pole invitations to lista emaili osób, które jeszcze nie odebrały wysłanego zaproszenia do znajomych."""
  email = db.EmailProperty(required=True)
  nick = db.StringProperty(required=True)
  firstname = db.StringProperty()
  lastname = db.StringProperty()
  is_male = db.BooleanProperty(required=True)
  invitations = db.StringListProperty()
  created_at = db.DateTimeProperty(auto_now=True)
  
  @property # @property zamienia user.nick_genitive() na user.nick_genitive
  def nick_genitive(self): return to_genitive(self.nick, self.is_male)
  @property
  def fullname(self): return self.firstname.capitalize() + " " + self.lastname.capitalize() if (self.firstname and self.lastname) else ""
  @property
  def fullname_genitive(self): return to_genitive(self.firstname, self.is_male).capitalize() + " " + to_genitive(self.lastname, True).capitalize() if (self.firstname and self.lastname) else ""
  @property
  def name(self): return self.fullname if self.fullname else self.nick
  @property
  def name_genitive(self): return self.fullname_genitive if (self.firstname and self.lastname) else self.nick_genitive()

  @property
  def avatar(self): return gravatar(self.email, 24)
  @property
  def photo(self): return gravatar(self.email, 150)
  
  @property
  def friends(self):
    """Zwraca zbiór friendów bez wyliczonego realative_saldo (patrz niżej: friends_with_relative_saldos)"""
    return Friend.gql("WHERE owner = :1", self.email).fetch(1000) # z Google Datastore można pobrać na raz max 1000 rekordów
  
  def find_friend_by_email(self, email):
    return Friend.gql("WHERE owner = :1 and email = :2", self.email, email).get()
  
  def find_friend_by_nick(self, nick):
    return Friend.gql("WHERE owner = :1 and nick = :2", self.email, nick).get()
  
  @property
  def friends_with_relative_saldos(self):
    """Zwraca zbiór friendów z wyliczonym polem relative_saldo.
    Przykład:
    Jeśli Kraxi kupuje pizzę za 20zł dla Jędrzeja i Rava, to z punktu widzenia Jędrzeja, Kraxi ma saldo 10zł a relative_saldo 20zł.
    Opcja 1:
    Zapis relative_saldo w bazie w momencie dodania zaqpka wymaga
    (zakładając że każda osoba ma 10 znajomych a w zaqpku bierze udział 5 osób)
    od 25 do 75 zapytań w zależności od rozkładu grup znajomych.
    70 na 75 z nich to zapis, który musi być przeprowadzany osobno dla każdego modelu. Może kiedyś to się zmieni.
    UPDATE!!!: http://googleappengine.blogspot.com/2009/06/10-things-you-probably-didnt-know-about.html - punkt 5.
    Opcja 2:
    Obliczenie relative_saldo w momencie wyświetlenia strony to tyle zapytań do bazy ilu znajomych na liście. Dla 10: 10.
    Odpadają zapytania modyfikujące relative_saldo w momencie usuwania zaqpka, dodawania i usuwania znajomych.
    Odpada również kod, który za to odpowiada.
    Wnioski:
    Nie zapisuję relative_saldo w bazie, tylko wyliczam na rządanie.
    Optymalizacja:
    Nie da się zajechać jednym zapytaniem - to nie baza relacyjna.
    Google DataStore: http://code.google.com/intl/pl/appengine/docs/python/datastore/
    Możliwe, że istnieje sposób na zmniejszenie ilości zapytań, którego w tej chwili nie znam.
    Mamy za darmo 10 000 000 zapytań dziennie więc na razie powinno wystarczyć.
    Jeśli userzy mają średnio po 10 znajomych i odświeżają stronę 10x dziennie to pomieścimy ich trochę mniej niż 10 000.
    W razie wyczerpywania się limitów jest jakieś cache'owanie poza bazą i ajax, a ostatecznie podniesienie limitów za kasę.
    """
    friends = {} # friends['jercik@gmail.com'] #=> obiekt Friend przedstawiający Jercika
    for f in self.friends: friends[f.email] = f # zapełniamy hasha friends friendami
    emails = friends.keys() # emaile znajomych
    for email in emails:
      # dla każdego znajomego f1:
      for f in friends.values() if email == self.email else Friend.gql("WHERE owner = :1", email).fetch(1000):
        # pobieramy każdego jego znajomego f2 i dla każdej takiej pary:
        if f.email in emails: # jeśli f1 i f2 są naszymi znajomymi: 
          friends[f.email].relative_saldo += f.saldo # uwzględniamy saldo f1 -> f2
    #sortowanie
    result = friends.values()
    result.sort(lambda f1, f2: int(f1.relative_saldo - f2.relative_saldo))
    
    # zaokrąglamy
    for f in result:
      f.relative_saldo = "%.2f" % round(0 if (f.relative_saldo < 0 and f.relative_saldo > -0.01) else f.relative_saldo, 2)
    
    return result
    
  def last_transfers(self, page=1, count=10):
    """Zwraca kilka ostatnich zaqpków"""
    offset = (page-1)*count
    first1000 = Transfer.gql("WHERE users = :1 ORDER BY created_at DESC", self.email).fetch(1000)
    if (offset + count) <= 1000:
      return first1000[offset:offset+count]
    else:
      last_date = first1000[-1].created_at
      def find(offset, count, last_date):
        transfers = Transfer.gql("WHERE users = :1 AND created_at < :2 ORDER BY created_at DESC", self.email, last_date).fetch(1000)
        if (offset + count) <= 1000:
          return transfers[offset:offset+count]
        elif (offset > 1000):
          find(offset-1000, count, transfers[-1].created_at)
        else:
          find(0, count, transfers[1000-offset+count])
          
      return find(offset-1000, last_date)
  
  def add_friend(self, recipient_email, nick=""):
    """Wysyła zaproszenie, przyjmuje zaproszenie albo nie robi nic w zależności od okoliczności"""
    recipient_email = recipient_email.lower()
    if not is_email(recipient_email) or recipient_email == self.email or recipient_email in self.invitations: return False # złe dane wejściowe
      
    f = Friend.gql("WHERE owner = :2 and email = :1", self.email, recipient_email).get()
    if f: return False # jesteście już znajomymi
    
    if nick and nick in map(lambda f: f.nick, self.friends): return False # masz już znajomego z takim nickiem
    
    recipient = User.gql("WHERE email = :1", recipient_email).get()
    if recipient and self.email in recipient.invitations: # przyjmujemy zaproszenie
      f1 = Friend(owner = self.email, email = recipient.email, nick = nick or recipient.nick, is_male = recipient.is_male)
      f2 = Friend(owner = recipient.email, email = self.email, nick = self.email  , is_male = self.is_male)
      recipient.invitations.remove(self.email)
      for record in [f1, f2, recipient]: record.put()
    else: # wysyłamy zaproszenie
      self.invitations.append(recipient_email)
      self.put()
      if not recipient: pass # TODO wysłanie zapro na maila
    return True
  
  def delete_friend(self, email):
    """Olewa zaproszenie, wywala znajomego albo nie robi nic w zależności od okoliczności"""
    email = email.lower()
    if not is_email(email): return False
    if email == self.email: return False
    else:
      if email in self.invitations: # usuwamy wysłane przez nas zaproszenie
        self.invitations.remove(email)
        self.put()
        return True
      user = User.gql("WHERE email = :1", email).get()
      if not user: return False # złe dane wejściowe
      if self.email in user.invitations: # olewamy zaproszenie
        user.invitations.remove(self.email)
        user.put()
        return True
      f1 = Friend.gql("WHERE owner = :1 and email = :2", self.email, email).get()
      if f1: # usuwamy frienda - interfejs graficzny tego na razie nie umożliwia
        f2 = Friend.gql("WHERE owner = :2 and email = :1", self.email, email).get()
        f1.delete()
        f2.delete()
        return True
      return False
  
  def delete_transfer(self, t):
    # modyfikujemy salda
    single_cost = t.cost/len(t.spongers)
    for sponsor_friend in filter(lambda f: f.email in t.spongers, Friend.gql("WHERE owner = :1", t.sponsor).fetch(1000)):
      sponsor_friend.saldo += single_cost
      sponsor_friend.put()
    for sponger_friend in filter(lambda f: f.owner in t.spongers, Friend.gql("WHERE email = :1", t.sponsor).fetch(1000)):
      sponger_friend.saldo -= single_cost
      sponger_friend.put()
    t.delete()
  
  def add_transfer(self, name, cost, spongers, sponsor):
    """Dodawanie zaqpka. Obsługuje niezpreparowane dane prosto z przeglądarki."""
    if not name or not cost or not spongers or not sponsor: return False # błędne dane, np. puste stringi
    
    try: cost = float(cost.replace(',', '.'))
    except: return False # koszt ma niepoprawy format
    
    # porządkujemy spongersów:
    # 'jerozy, ; ,     , kraxiego   , poskarta' #=> ['jerozy', 'kraxiego', 'poskarta']
    # usuwamy puste stringi
    # usuwamy duplikacje
    spongers = list(set(filter(lambda s: s, map(lambda s: s.strip().lower(), spongers.replace(';', ',').split(',')))))
    
    sponsor = sponsor.strip().lower()
    
    friends = self.friends # wyciągamy z bazy znajomych, bo self.friends ich nie cache'uje
    def nick_genitive_to_email(sponger):
      # 'jercika' #=> 'jercik@gmail.com'
      # 'jercik@gmail.com' #=> 'jercik@gmail.com'
      return sponger if is_email(sponger) else filter(lambda f: f.nick_genitive.upper() == sponger.upper(), friends)[0].email
    try:
      spongers = map(nick_genitive_to_email, spongers) # zamieniamy nicki na emaile: ['jercik@gmail.com', 'kraxiego'] => ['jercik@gmail.com', 'm.krakowiak@gmail.com']
      sponsor = nick_genitive_to_email(sponsor) # j.w.
    except: return False # nie znaleziono znajomego o podanej nazwie
    # sprawdzamy czy sponsor zna każdego spongera
    sponsor_friends = Friend.gql("WHERE owner = :1", sponsor).fetch(1000)
    sponsor_friends_emails = [s.email for s in sponsor_friends]
    for s in spongers:
      if not s in sponsor_friends_emails:
        return False # nie zna
        
    snitch = self.email
    users = list(set(spongers + [sponsor] + [snitch])) # cache'ujemy wszystkich userów w jednym miejscu, żeby móc wyciągać zaqpki danego usera jednym zapytaniem bez względu na to jaką rolę w nich pełnił
    Transfer(name = name, cost = cost, spongers = spongers, sponsor = sponsor, snitch = snitch, users = users).put()
    # aktualizacja sald (ilość userów * 2 + 2) zapytań
    # aktualizujemy wszystkie wektorki sald od sponsora do spongera i vice versa
    # TODO nie wyciągać 2. raz friendów current_usera
    single_cost = cost/len(spongers)
    for sponsor_friend in filter(lambda f: f.email in spongers, sponsor_friends):
      sponsor_friend.saldo -= single_cost
      sponsor_friend.put()
    for sponger_friend in filter(lambda f: f.owner in spongers, Friend.gql("WHERE email = :1", sponsor).fetch(1000)):
      sponger_friend.saldo += single_cost
      sponger_friend.put()
    return True
    
class Friend(db.Model):
  """Znajomy. Relacja symetryczna. Zawiera saldo pomiędzy właścicielem i celem w oczach właściciela.
  Jeśli to jest Rav w oczach Jędrzeja, który kupił jędrzejowi gumę Boomer za 50 groszy to saldo wynosi 0.5
  Pole relative_saldo wylicza się w User::friends_with_relative_saldos"""
  email = db.EmailProperty(required=True) # email Rava
  owner = db.EmailProperty(required=True) # email Jędrzeja
  saldo = db.FloatProperty(default=0.0)
  nick = db.StringProperty(required=True)
  is_male = db.BooleanProperty(required=True)
  created_at = db.DateTimeProperty(auto_now=True)
  relative_saldo = 0.0 # pole które należy zmodyfikować przed użyciem
  
  @property
  def nick_genitive(self): return to_genitive(self.nick, self.is_male)
  @property
  def self(s): return s.owner == s.email
  @property
  def avatar(self): return gravatar(self.email, 24)
  @property
  def photo(self): return gravatar(self.email, 150)

class Transfer(db.Model):
  """Zaqpek"""
  cost = db.FloatProperty(required=True)
  name = db.StringProperty(required=True) # nazwa zaqpka
  sponsor = db.EmailProperty(required=True)
  spongers = db.StringListProperty() # lista emaili spongerów (nie ma db.EmailListProperty())
  users = db.StringListProperty() # spongers + sponsor + snitch
  snitch = db.EmailProperty(required=True)
  created_at = db.DateTimeProperty(auto_now=True)
  even = '' # do uzupełnienia

class Handler(webapp.RequestHandler):
  """Klasa, po której dziedziczą 'kontrolery'.
  Zawiera głównie helper do generowania widoków i funkcje weryfikujące czy jesteśmy zalogowani/zarejestrowani.
  1 handler to 1 url i max 4 różne akcje (get, post, put, delete)."""
  
  def view(self, name, values = {}):
    """Generowanie widoku z templejta"""
    path = os.path.join(os.path.dirname(__file__), name)
    self.response.out.write(template.render(path, values))
  
  def redirect_to_login(self): self.redirect(users.create_login_url(self.request.uri))
  def redirect_to_signup(self): self.redirect('/signup')
  def logout_url(self): return users.create_logout_url(self.request.uri)
  
  def authorized(self):
    """Sprawdza czy użytkownik jest zalogowany na konto gmaila.
    Jeśli nie, ustawia redirect na url logowania."""
    if users.get_current_user():
      self.current_email = users.get_current_user().email().lower()
      return True
    else:
      self.redirect_to_login()
      return False # po nieudanum authorize trzeba dać return
  
  def is_admin(self):
    return users.is_current_user_admin()
  
  def signed_up(self):
    """Sprawdza czy użytkownik jest zarejestrowany w naszej bazie.
    Jeśli nie jest zalogowany na konto gmaila, ustawia redirect na url logowania.
    Jeśli jest zalogowany ale nie nie ma konta, ustawia redirect na url rejestracji."""
    if self.authorized():
      email = users.get_current_user().email().lower()
      user = User.gql("WHERE email = :1", email).get()
      if user:
        self.current_user = user
        return True
      else:
        self.redirect_to_signup()
        return False # po nieudanym sign_up trzeba dać return

class SignupHandler(Handler):
  """Rejestracja"""
  
  def view(self, email, nick = "", firstname = "", lastname = "", is_male = False, error = False):
    """Przeciążona funkcja z klasy Handler.
    Wyciąga możliwie dużo informacji z emaila i wyświetla widok."""
    
    # sprawdza czy da się wyciągnąć imię i nazwisko z emaila
    def is_fullname_email(email): return re.match('^([a-zA-Z]+)[\.\-\_]([a-zA-Z]+)@((?:[-a-z0-9]+\.)+[a-z]{2,})$', email)
    firstname = firstname or is_fullname_email(email) and is_fullname_email(email).group(1).capitalize() or ''
    lastname = lastname or is_fullname_email(email) and is_fullname_email(email).group(2).capitalize() or ''
    nick = nick or firstname or is_email(email).group(1).capitalize()
    is_male = is_male or firstname and not re.match('a$', firstname) # jeśli imię nie kończy się na "a" to facet
    Handler.view(self, 'signup.html', {'email': email, 'gravatar': gravatar(email, 150), 'nick': nick, 'firstname': firstname, 'lastname': lastname, 'is_male': is_male, 'logout_url': self.logout_url(), 'error': error})
  
  def get(self):
    if not self.authorized(): return
    if not (User.gql("WHERE invitations = :1", self.current_email.lower()).get() or PermittedEmail.gql("WHERE email = :1", self.current_email.lower()).get()):
        logging.info(str(self.current_email) + " próbuje dostać się do Zaqpków.")
        Handler.view(self, 'not_permitted.html', {'logout_url': self.logout_url()})
    else:
      self.view(self.current_email)
    
  def post(self):
    if not self.authorized(): return
    email = self.current_email
    nick, firstname, lastname = self.request.get('nick'), self.request.get('firstname'), self.request.get('lastname')
    is_male =  self.request.get('sex') != 'female'
    if not (User.gql("WHERE invitations = :1", self.current_email.lower()).get() or PermittedEmail.gql("WHERE email = :1", self.current_email.lower()).get()):
      return self.redirect_to_login()
    try:
      User(email = email, nick = nick, firstname = firstname, lastname = lastname, is_male = is_male).put()
      Friend(owner = email, email = email, nick = nick, is_male = is_male).put()
      self.redirect('/')
    except db.BadValueError:
      self.view(email, nick, firstname, lastname, is_male)

class Cycle(object):
  """Wyświetlany cyklicznie zwraca '' na przemian z 'even'"""
  def __init__(self, text = 'even', fromFirst = False):
    self.text = 'even'
    self.i = 1 if fromFirst else 0
  def __str__(self):
    self.i = 1 - self.i
    return self.text if self.i == 0 else ''

class MainHandler(Handler):
  """Dashboard"""
  def get(self, page = 1, count = 10):
    page = int(page)
    if not self.signed_up(): return
    invitation_sender = User.gql("WHERE invitations = :1", self.current_user.email.lower()).get()
    if invitation_sender:
      self.view('invitation.html', {'invitation_sender': invitation_sender})
      return
    else:
      friends = self.current_user.friends
      def email_to_nick_genitive(email, memory = {}):
        """Zwraca nick w dopełniaczu dla podanego emaila. Zapamiętuje zwracane wyniki."""
        if memory.get(email): return memory[email]
        results = filter(lambda f: f.email.lower() == email.lower(), friends)
        memory[email] = results[0].nick_genitive if len(results) else email
        return memory.get(email)
      # tworzymy strukturę: [{name: n, cost: c, spongers: [{avatar: a1, nick: n1}, {avatar: a2, nick: n2}, ...], sponsor: s}, ...]
      def is_self(email): return email == self.current_user.email
      last_transfers = self.current_user.last_transfers(page)
      if not len(last_transfers) and page != 1: return self.redirect('/')
      transfers = [Hash({'name': t.name,
                         'cost': "%.2f" % round(t.cost, 2),
                         'date': parse_date(t.created_at),
                         'key': t.key,
                         'spongers': [Hash({'avatar': gravatar(s),
                                            'nick': email_to_nick_genitive(s),
                                            'self': is_self(s)
                                            }) for s in t.spongers],
                         'sponsor': Hash({'avatar': gravatar(t.sponsor),
                                          'nick': email_to_nick_genitive(t.sponsor),
                                          'self': is_self(t.sponsor)}),
                          }) for t in last_transfers]
      last_tester = None
      if self.is_admin():
        last_tester = PermittedEmail.gql("ORDER BY created_at DESC").get()
      self.view('index.html', {'is_admin': self.is_admin(), 'last_tester': last_tester, 'newer_available': page != 1, 'older_available': len(last_transfers) >= count, 'newer_page': page-1, 'older_page': page+1, 'current_user': self.current_user, 'transfers': transfers, 'even': Cycle(), 'even2': Cycle(), 'small': gravatar('jercik@gmail.com', 24), 'logout_url': self.logout_url()})

class AddFriendHandler(Handler):
  def post(self):
    if not self.signed_up(): return
    self.current_user.add_friend(self.request.get('email'), self.request.get('nick'))
    self.redirect('/')
    
class DeleteFriendHandler(Handler):
  def post(self):
    if not self.signed_up(): return
    self.current_user.delete_friend(self.request.get('email'))
    self.redirect('/')

class AddTransferHandler(Handler):
  def post(self):
    if not self.signed_up(): return
    self.current_user.add_transfer(self.request.get('name'), self.request.get('cost'), self.request.get('spongers'), self.request.get('sponsor'))
    self.redirect('/')

class ProfileHandler(Handler):
  def get(self):
    if not self.signed_up(): return
    self.view('profile.html', {'user': self.current_user})

class ShowFriendHandler(Handler):
  def get(self, key):
    if not self.signed_up(): return
    if not key: return self.redirect('/')
    friend = Friend.gql("WHERE __key__ = :1", db.Key(key)).get()
    if not friend or friend.owner != self.current_user.email: return self.redirect('/')
    if friend.email == self.current_user.email:
      return self.redirect('/profile')
    else:
      user = User.gql("WHERE email = :1", friend.email).get()
      if not user: return self.redirect('/')
      self.view('friend.html', {'friend': friend, 'user': user})

class EditFriendHandler(Handler):
  def post(self):
    if not self.signed_up(): return
    email = self.request.get('email')
    if not email: return self.redirect('/')
    nick = self.request.get('nick')
    friend = self.current_user.find_friend_by_email(email)
    if not friend: return self.redirect('/')
    
    # sprawdzanie duplikacji nicków
    if len(filter(lambda f: f.nick == nick, self.current_user.friends)): return self.redirect('/')
    
    friend.nick = nick
    friend.put()
    
    if email.upper() == self.current_user.email.upper():
      # profil
      self.current_user.nick = nick
      self.current_user.firstname = self.request.get('firstname')
      self.current_user.lastname = self.request.get('lastname')
      self.current_user.is_male = self.request.get('sex') != 'female'
      self.current_user.put()
      
    self.redirect('/')

class DeleteTransferHandler(Handler):
  def get(self, key):
    if not self.signed_up(): return
    if not key: return self.redirect('/')
    t = Transfer.gql("WHERE __key__ = :1", db.Key(key)).get()
    if not t: return self.redirect('/')
    if not self.current_user.email in t.users: return self.redirect('/')
    self.current_user.delete_transfer(t)
    self.redirect('/')

class PermittedEmail(db.Model):
  email = db.EmailProperty()
  created_at = db.DateTimeProperty(auto_now=True)

class SetupHandler(Handler):
  def get(self):
    email = 'zaqpkipl@gmail.com'
    permitted_email = PermittedEmail.gql("WHERE email = :1", email).get()
    if not permitted_email:
      PermittedEmail(email = email).put()
    return self.redirect('/')

class AddEmailHandler(Handler):
  def post(self):
    if not self.is_admin(): return self.redirect('/')
    email = self.request.get('email')
    if not email: return self.redirect('/')
    email = email.strip().lower()
    if not is_email(email): return self.redirect('/')
    permitted_email = PermittedEmail.gql("WHERE email = :1", email).get()
    if not permitted_email:
      PermittedEmail(email = email).put()
    return self.redirect('/')
    

application = webapp.WSGIApplication([('/', MainHandler),
                                      (r'/page/(.*)', MainHandler),
                                      ('/signup', SignupHandler),
                                      (r'/friends/show/(.*)', ShowFriendHandler),
                                      ('/friends/add', AddFriendHandler),
                                      ('/friends/edit', EditFriendHandler),
                                      ('/friends/delete', DeleteFriendHandler),
                                      ('/profile', ProfileHandler),
                                      ('/transfers/add', AddTransferHandler),
                                      (r'/transfers/delete/(.*)', DeleteTransferHandler),
                                      ('/setup', SetupHandler),
                                      ('/admin/emails/add', AddEmailHandler)
                                      ],
                                      debug=True)

if __name__ == '__main__': run_wsgi_app(application)
