import os, json
import genanki
from collections import defaultdict

def link_wrap(text, href, title=None):
	if title is None:
		title = text
	return f'<a href="{href}" title="{title}">{text}</a>'

class StableNote(genanki.Note):
	@property
	def guid(self):
		return genanki.guid_for(self.fields[0], self.fields[1])

CSS = """
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
	def __init__(self, filename, uma_folder):
		self.filename = filename
		self.uma_folder = uma_folder
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
			css=CSS
		)

		self.deck = genanki.Deck(1810934977, 'Umamusume')

	def add_card(self, name, outfit):
		safe_name = name.replace(" ", "_")
		img_name = f"{safe_name}_({outfit}).png"
		src_path = os.path.join(self.uma_folder, name, img_name)
		if not os.path.exists(src_path):
			print(f"Warning: source image not found: {src_path}")
			return

		self.media_files.append(src_path)
		imageTag = f'<img src="{os.path.basename(src_path)}">'

		attributes_path = os.path.join(self.uma_folder, name, "attributes.json")
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

def parse_folder(uma_folder):
	all_umas = []
	teams = defaultdict(list)

	for name in os.listdir(uma_folder):
		folder_path = os.path.join(uma_folder, name)
		if not os.path.isdir(folder_path):
			continue

		all_umas.append(name)

		attributes_path = os.path.join(folder_path, "attributes.json")
		if not os.path.exists(attributes_path):
			continue

		with open(attributes_path, "r", encoding="utf-8") as f:
			attrs = json.load(f)
		
		if "Teams" not in attrs:
			continue

		for team in attrs["Teams"].split(","):
			teams[team].append(name)

	return all_umas, teams

def generate_deck(uma_folder):
	all_umas, teams = parse_folder(uma_folder)
	team_members = set(sum(teams.values(), []))
	deck = AnkiDeck(filename="umamusume.apkg", uma_folder=uma_folder)

	for outfit in ["Race", "Main", "Stage", "Proto"]:
		for team, names in teams.items():
			for name in names:
				safe_name = name.replace(" ", "_")
				img_name = f"{safe_name}_({outfit}).png"
				img_path = os.path.join(name, img_name)
				full_path = os.path.join(uma_folder, img_path)
				if os.path.exists(full_path):
					deck.add_card(name, outfit)
		for name in all_umas:
			if name in team_members:
				continue
			safe_name = name.replace(" ", "_")
			img_name = f"{safe_name}_({outfit}).png"
			img_path = os.path.join(name, img_name)
			full_path = os.path.join(uma_folder, img_path)
			if os.path.exists(full_path):
				deck.add_card(name, outfit)	

	return deck

def main():
	deck = generate_deck("uma_musume")
	print("saving deck...", end=" ", flush=True)
	deck.save()
	print("done")

if __name__ == "__main__":
	main()