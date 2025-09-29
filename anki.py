import os, json, random, sqlite3, zipfile, tempfile, shutil
import genanki
from datetime import datetime
from collections import defaultdict

OUTFITS = {
	"Main": "Uniform",
	"Race": "Race",
	"Stage": "Stage",
	"Proto": "Prototype"
}

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

def link_wrap(text, href, title=None):
	if title is None:
		title = text
	return f'<a href="{href}" title="{title}">{text}</a>'

class StableNote(genanki.Note):
	@property
	def guid(self):
		return genanki.guid_for(self.fields[0], self.fields[1])

class UmaDeck(genanki.Deck):
	def __init__(self, uma_folder, outfit):
		deck_name = f"{uma_folder.capitalize()} - {OUTFITS[outfit]}"
		random.seed(deck_name)
		deck_id = random.randrange(1 << 30, 1 << 31)

		super().__init__(deck_id, deck_name)

		self.outfit = outfit
		self.uma_folder = uma_folder
		self.uma_media_files = []

		self.uma_model = genanki.Model(
			1749272173,
			'Umamusume Model',
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

	def add_note(self, name):
		safe_name = name.replace(" ", "_")
		img_name = f"{safe_name}_({self.outfit}).png"
		src_path = os.path.join(self.uma_folder, name, img_name)
		if not os.path.exists(src_path):
			print(f"Warning: source image not found: {src_path}")
			return

		self.uma_media_files.append(src_path)
		imageTag = f'<img src="{os.path.basename(src_path)}">'

		attributes_path = os.path.join(self.uma_folder, name, "attributes.json")
		attributes_html = ''
		if os.path.exists(attributes_path):
			attributes_html += '<table class="infobox"><tbody>'

			with open(attributes_path, "r", encoding="utf-8") as f:
				attributes = json.load(f)

			key_order = [
				"Japanese", "Nicknames", "Title",
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
		note = StableNote(model=self.uma_model, fields=[imageTag, name_html, attributes_html])
		super().add_note(note)

	def inject_description(self, apkg_path):
		tmpdir = tempfile.mkdtemp()
		with zipfile.ZipFile(apkg_path, 'r') as zf:
			zf.extractall(tmpdir)

		db_path = os.path.join(tmpdir, 'collection.anki2')
		conn = sqlite3.connect(db_path)
		c = conn.cursor()
		c.execute("SELECT decks FROM col")
		decks_json, = c.fetchone()
		import json
		decks = json.loads(decks_json)

		str_deck_id = str(self.deck_id)
		if str_deck_id in decks:
			decks[str_deck_id]['desc'] = self.description
			c.execute("UPDATE col SET decks = ?",
					(json.dumps(decks, ensure_ascii=False, separators=(',', ':')),))
			conn.commit()

		conn.close()

		new_apkg = apkg_path
		with zipfile.ZipFile(new_apkg, 'w') as zf:
			for root, _, files in os.walk(tmpdir):
				for file in files:
					full_path = os.path.join(root, file)
					rel_path = os.path.relpath(full_path, tmpdir)
					zf.write(full_path, rel_path)

		shutil.rmtree(tmpdir)

	def save(self):
		package = genanki.Package(self)
		package.media_files = self.uma_media_files
		filename = f"{self.name}.apkg"
		package.write_to_file(filename)
		self.inject_description(filename)

		md_filename = f"{self.name}.md"
		with open(md_filename, "w", encoding="utf-8") as f:
			f.write(self.description)

def parse_folder(uma_folder):
	all_umas = []
	teams = defaultdict(list)
	dorms = set()

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

		if "Teams" in attrs:
			for team in attrs["Teams"].split(","):
				teams[team].append(name)

		if "Dorm" in attrs and attrs["Dorm"].strip():
			dorms.add(attrs["Dorm"].strip())

	random.seed(uma_folder)
	random.shuffle(all_umas)

	return all_umas, teams, dorms

def main():
	uma_folder = "umamusume"
	all_umas, teams, dorms = parse_folder(uma_folder)
	team_members = set(sum(teams.values(), []))

	for outfit in OUTFITS:
		deck = UmaDeck(uma_folder=uma_folder, outfit=outfit)
		missing_with_teams = []
		missing_without_teams = []

		def add_uma(name):
			safe_name = name.replace(" ", "_")
			img_name = f"{safe_name}_({outfit}).png"
			full_path = os.path.join(uma_folder, name, img_name)
			if os.path.exists(full_path):
				deck.add_note(name)
				return True
			return False

		for name in all_umas:
			if name in team_members:
				if not add_uma(name):
					missing_with_teams.append(name)

		for name in all_umas:
			if name not in team_members:
				if not add_uma(name):
					missing_without_teams.append(name)

		all_missing = missing_with_teams + missing_without_teams
		available_count = len(all_umas) - len(all_missing)
		missing_count = len(all_missing)
		team_available_count = len(team_members) - len(missing_with_teams)

		if missing_count > 0:
			missing_line = f" but the following ({missing_count}) [1]:\n- {'\n- '.join(all_missing)}"
		else:
			missing_line = " [1]"

		team_list = list(teams.keys())
		team_sample = ", ".join(team_list[:2]) + (", ..." if len(team_list) > 2 else "")
		dorm_sample = " or ".join(sorted(dorms))
		now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

		deck.description = f"""
Contains all characters under the "Umamusume" category with a {OUTFITS[outfit]} outfit of https://umamusu.wiki/List_of_Characters ({available_count}){missing_line}

It features:

- A card for each character in {OUTFITS[outfit]} outfit
- Gradual difficulty increase [2]
- The following attributes (in order):
  - Japanese: the katakana version of the name of the character
  - Nicknames: list of nicknames if any
  - Title: epithet of the character if any
  - Birthday: birth date of the character but the year
  - Height: height of the character in centimeters
  - Teams: teams the character is part of ({team_sample})
  - Dorm: dorm the character is part of ({dorm_sample})
  - Roommate: the roommate of the character if any
  - Voice Actor: the voice actor of the character in the anime

[1] Numbers were given at the time of latest update ({now})  
[2] The first characters to be added are ones that are in a team, {team_available_count} of them [1], then the rest, all in seeded randomized order

Credits:

Content is available under Creative Commons Attribution-ShareAlike unless otherwise noted. Umamusume: Pretty Derby contents and materials are trademarks and copyrights of Cygames, Inc.
""".strip()

		print(f"saving {deck.name} (id: {deck.deck_id})...", end=" ", flush=True)
		deck.save()
		print("done")

if __name__ == "__main__":
	main()
