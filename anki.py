import os
import genanki
import json

def link_wrap(text, href, title=None):
	if title is None:
		title = text
	return f'<a href="{href}" title="{title}">{text}</a>'

class StableNote(genanki.Note):
	@property
	def guid(self):
		return genanki.guid_for(self.fields[0], self.fields[1])

css = """
.frontbg {
    display: flex;
    justify-content: center;
    align-items: center;
    background: none;
    padding: 20px;
}

.backbg {
    display: flex;
    align-items: flex-start;
    background: none;
    padding: 20px;
}

.back-left {
    flex: 0 0 auto;
    margin-right: 40px;
}

.back-right {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
}

.name {
    font-family: 'Noto Sans JP', 'BIZ UDGothic', sans-serif;
    font-size: 48px;
    font-weight: bold;
    margin-bottom: 25px;
    color: #fff;
    text-align: left;
}

table.infobox {
    border-collapse: collapse;
    width: auto;
}

table.infobox td {
    border: none;
    font-size: 24px;
    color: #eee;
    padding: 6px 0;
    line-height: 1.8;
    text-align: left;
}

table.infobox td:first-child {
    width: 140px;   /* fixed width for keys */
    color: #ccc;
    font-weight: bold;
    padding-right: 100px; /* gap between key and value */
}

table.infobox td:last-child {
    text-align: left;
    width: auto;
}

a {
    color: #66ccff;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

img {
    display: block;
    height: auto;
    border-radius: 6px;
}
"""

class AnkiDeck:
	def __init__(self, filename, scrap_folder):
		self.filename = filename
		self.scrap_folder = scrap_folder
		self.media_files = []

		self.model = genanki.Model(
			1749272173,
			'UmaMusume Model',
			fields=[{'name': 'Image Tag'}, {'name': 'Name'}, {'name': 'Attributes'}],
			templates=[{
				'name': 'Card 1',
				'qfmt': '''
<div class="frontbg">
	{{Image Tag}}
</div>''',
			'afmt': '''
<div class="backbg">
    <div class="back-left">
        {{Image Tag}}
    </div>
    <div class="back-right">
        <div class="name">{{Name}}</div>
        {{Attributes}}
    </div>
</div>'''
			}],
			css=css
		)

		self.deck = genanki.Deck(1810934977, 'Umamusume')

	def add_card(self, name, outfit):
		safe_name = name.replace(" ", "_")
		img_name = f"{safe_name}_({outfit}).png"
		src_path = os.path.join(self.scrap_folder, name, img_name)
		if not os.path.exists(src_path):
			print(f"Warning: source image not found: {src_path}")
			return

		self.media_files.append(src_path)
		imageTag = f'<img src="{os.path.basename(src_path)}">'

		attributes_path = os.path.join(self.scrap_folder, name, "attributes.json")
		attributes_html = ''
		if os.path.exists(attributes_path):
			attributes_html += '<table class="infobox"><tbody>'

			with open(attributes_path, "r", encoding="utf-8") as f:
				attributes = json.load(f)

			key_order = [
				"Kana", "Nicknames", "Alias",
				"Birthday", "Height",
				"Teams", "Dorm", "Roommate",
				"Voice Actor"
			]

			for key in key_order:
				if not (key in attributes and attributes[key].strip()):
					continue
				value = attributes[key]

				if key == "Teams":
					teams_links = []
					for team in map(str.strip, value.split(",")):
						href = f"https://umamusu.wiki/Teams_and_Clubs#Team_{team.replace(' ', '_')}"
						teams_links.append(link_wrap(team, href))
					value = ", ".join(teams_links)
				elif key == "Dorm":
					href = f"https://umamusu.wiki/Roommates/{value.replace(' ', '_')}_Dorm"
					value = link_wrap(value, href)
				elif key in ["Roommate", "Voice Actor"]:
					href = f"https://umamusu.wiki/{value.replace(' ', '_')}"
					value = link_wrap(value, href)

				attributes_html += f'<tr><td><i>{key}</i></td><td>{value}</td></tr>'

			attributes_html += '</tbody></table>'

		name_html = link_wrap(name, f"https://umamusu.wiki/{name.replace(' ', '_')}")
		note = StableNote(model=self.model, fields=[imageTag, name_html, attributes_html])
		self.deck.add_note(note)

	def save(self):
		package = genanki.Package(self.deck)
		package.media_files = self.media_files
		package.write_to_file(self.filename)

teams = {
	"Team Spica": ["Special Week", "Silence Suzuka", "Tokai Teio", "Vodka",
				   "Gold Ship", "Daiwa Scarlet", "Mejiro McQueen"],
	"Team Rigil": ["Air Groove", "El Condor Pasa", "Grass Wonder", "Symboli Rudolf",
				   "Taiki Shuttle", "T.M. Opera O", "Narita Brian", "Hishi Amazon",
				   "Fuji Kiseki", "Maruzenski"],
	"Team Canopus": ["Nice Nature", "Twin Turbo", "Ikuno Dictus", "Matikane Tannhauser"]
}
team_members = set(sum(teams.values(), []))

scrap_folder = "scrap"
all_umas = [name for name in os.listdir(scrap_folder) if os.path.isdir(os.path.join(scrap_folder, name))]

deck = AnkiDeck(filename="umamusume.apkg", scrap_folder=scrap_folder)

for outfit in ["Race", "Main", "Stage", "Proto"]:
	for team, names in teams.items():
		for name in names:
			safe_name = name.replace(" ", "_")
			img_name = f"{safe_name}_({outfit}).png"
			img_path = os.path.join(name, img_name)
			full_path = os.path.join(scrap_folder, img_path)
			if os.path.exists(full_path):
				deck.add_card(name, outfit)
	for name in all_umas:
		if name in team_members:
			continue
		safe_name = name.replace(" ", "_")
		img_name = f"{safe_name}_({outfit}).png"
		img_path = os.path.join(name, img_name)
		full_path = os.path.join(scrap_folder, img_path)
		if os.path.exists(full_path):
			deck.add_card(name, outfit)

print("saving deck...", end=" ", flush=True)
deck.save()
print("done")