<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
	"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
	<head>
		<meta http-equiv="Content-type" content="text/html; charset=utf-8">
		<title>Zaqpki</title>
		
		<script src="/javascripts/jquery.js" type="text/javascript" charset="utf-8"></script>
		<script src="/javascripts/jquery.autocomplete.js" type="text/javascript" charset="utf-8"></script>
		<script src="/javascripts/jquery.tools.js" type="text/javascript" charset="utf-8"></script>
		
		<link rel="icon" href="/images/small/shopping_cart.png" type="image/png">
		
		<link rel="stylesheet" href="/stylesheets/jquery.autocomplete.css" type="text/css" media="screen" charset="utf-8" />
		<link rel="stylesheet" href="/stylesheets/dashboard.css" type="text/css" media="screen" charset="utf-8" />
		<script type="text/javascript" charset="utf-8">
			function calculate_input_value(inp){
				try{
					inp.value = inp.value ? Math.round(eval(inp.value.replace(/,/g, '.'))*100)/100 : ''
				} catch(e) {
					window.alert("Błąd w polu ceny! \n Niepoprawny format: " + inp.value)
				}
			}
		
			$(function(){
				$('input[type=text].hint').tooltip({
					position: ['top', 'left'], 
					offset: [1, 5],
					effect: 'toggle'
				})
				var friends = [];
				{% for friend in current_user.friends %}
					friends.push("{{ friend.nick_genitive }}");
				{% endfor %}
				$("#spongers").autocomplete(friends, {
					minChars: 0,
					multiple: true,
					mustMatch: true,
					width: 295
				});
				$("#sponsor").autocomplete(friends, {
					minChars: 0,
					multiple: false,
					mustMatch: true,
					width: 100
				})
				$("#name").val("");
				$("#cost").val("");
				$("#cost").focus();
			});
		</script>
	<body>
	  <div id="container">
			<div id="header">
			</div>
			<div id="topbar">
				<div class="main">
					<div id="add_transfer">
				    <form action="/transfers/add" method="post">
							<span class="input">
								<input class="hint" id="cost" type="text" name="cost" value="" size=2 onblur="calculate_input_value(this)"/><div class="tooltip">
									Cena
								</div> zł za
								<input class="hint" id="name" type="text" name="name" value="" size=9 /><div class="tooltip">
									Nazwa
								</div>
								dla <input class="hint" type="text" name="spongers" id="spongers" value="" size=30 /><div class="tooltip">
									Dla
								</div>
								od <input class="hint" type="text" name="sponsor" id="sponsor" size=8 value="{{ current_user.nick_genitive }}" /><div class="tooltip">
									Od
								</div>
							</span>
							<input type="submit" value="Dodaj"/>
						</form>
				  </div>
				</div>
				<div class="side">
					<div id="add_friend">
						<form method="POST" action="/friends/add">
							<span class="input">
				      	<input class="hint add_email" id="email" name="email" type="text" size="14"/><div class="tooltip">
									Email
								</div>
				      </span>
							<input type="submit" value="Dodaj"/>
				    </form>
					</div>
				</div>
			</div>
			<div class="main">
				<div id="transfers">
					{% for transfer in transfers %}
						<div class="transfer {{ even }}">
							<span class="cost">{{ transfer.cost }} zł</span> za
							<span class="name">{{ transfer.name }}</span>
							dla
							{% for sponger in transfer.spongers %}
								<span class="sponger {% if sponger.self %}self{% endif %}"><img src="{{ sponger.avatar }}"></img>{{ sponger.nick }}</span>
							{% endfor %}
							od <span class="sponsor {% if transfer.sponsor.self %}self{% endif %}">
								<img src="{{ transfer.sponsor.avatar }}"></img>{{ transfer.sponsor.nick }}</span>
								<span class="date">{{ transfer.date }}</span>
								<span class="controlls">
								<a href="/transfers/delete/{{ transfer.key }}"><img src="/images/small/trash_can.png"></img></a>
							</span>
						</div>
					{% endfor %}
					{% if not transfers %}
						<div class="transfer empty">
							Brak zaqpków
						</div>
					{% endif %}
				</div>
				<div class="main bottombar">
					{% if newer_available %}
						<a href="/page/{{ newer_page }}"><img src="/images/small/back.png"/>Nowsze</a>
					{% endif %}
					{% if older_available %}
						<a href="/page/{{ older_page }}">Starsze<img src="/images/small/next.png"/></a>
					{% endif %}
				</div>
			</div>
			<div class="side">
			  <div id="friends">
					{% for friend in current_user.friends_with_relative_saldos %}
						<div class="friend {{ even2 }} {% if friend.self %} self {% endif %}">
							<div class="nick"><a href="/friends/show/{{ friend.key }}"><img src="{{ friend.avatar }}"></img>
								{{ friend.nick }}
								</a></div>
							<div class="saldo">
								{{ friend.relative_saldo }} zł
							</div>
						</div>
					{% endfor %}
					{% for invitation in current_user.invitations %}
						<div class="invitation {{ even2 }}">
							<div class="email">
								{{ invitation }}
							</div>
							<div class="controlls">
								<form action="/friends/delete" method="post">
									<input type="hidden" name="email" value="{{ invitation }}"/>
									<input type="submit" value="usuń"/>
								</form>
							</div>
						</div>
					{% endfor %}
				</div>
				<div class="side bottombar">
					{% if is_admin %}
					<a href="https://appengine.google.com/datastore/explorer?app_id=zaqpkipl&kind=PermittedEmail&limit=20&offset=0&query=SELECT%20*%20FROM%20PermittedEmail&viewby=kind"><img src="/images/small/search_database.png" /></a>
					{% endif %}
					<a href="{{ logout_url }}"><img src="/images/small/unlock.png"></img>Wyloguj</a>
				</div>
			</div>
		</div>
	</body>
</html>
