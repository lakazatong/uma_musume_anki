import os, pickle, requests, time, json, re
from urllib.parse import unquote
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

CACHE_FILE = "cache.pkl"
OUT_FOLDER = "umamusume"
CACHE = {}
DELAY = 1 # seconds
TTL = 7 * 24 * 60 * 60 # 7 days
BASE_URL = "https://umamusu.wiki"
ATTRIBUTES = {
	"Japanese": None,
	"Nicknames": lambda x: ", ".join(
		part.strip() for part in re.split(r"<br\s*/?>", x) if part.strip()
	),
	# Title will be filled later

	"Birthday": None,
	"Height": None,

	# Teams will be filled later
	"Dorm": None,
	"Roommate": lambda x: BeautifulSoup(x, "html.parser").get_text(strip=True),

	"Voice Actor": lambda x: BeautifulSoup(x, "html.parser").get_text(strip=True),
	# Game ID will be filled later
}
DORMS = ["Miho", "Ritto"]

def load_cache():
	global CACHE
	if os.path.exists(CACHE_FILE):
		print("loading cache...", end=" ", flush=True)
		with open(CACHE_FILE, "rb") as f:
			CACHE = pickle.load(f)
		print("done")

def save_cache():
	print("saving cache...", end=" ", flush=True)
	with open(CACHE_FILE, "wb") as f:
		pickle.dump(CACHE, f)
	print("done")

def load_page(url):
	now = time.time()
	if url in CACHE:
		fetched_time, soup = CACHE[url]
		if now - fetched_time < TTL:
			return soup
	print(f"Fetching page: {url}")
	time.sleep(DELAY)
	r = requests.get(url)
	soup = BeautifulSoup(r.text, "html.parser")
	CACHE[url] = (now, soup)
	return soup

def crop_transparent_pixels(im):
	try:
		if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
			alpha = im.split()[-1]
			bbox = alpha.getbbox()
			if bbox:
				im = im.crop(bbox)
		return im
	except Exception as e:
		print(f"Failed to crop image: {e}")
		return im

def download_img(url, dest_path):
	decoded_name = os.path.join(os.path.dirname(dest_path), unquote(os.path.basename(dest_path)))
	if os.path.exists(decoded_name):
		return
	print(f"Downloading image: {decoded_name}")
	time.sleep(DELAY)
	r = requests.get(url)
	im = Image.open(BytesIO(r.content))
	im = crop_transparent_pixels(im)
	im.save(decoded_name)
	im.close()

def find_next_sibling(start, cond):
	sibling = start.find_next_sibling()
	while sibling:
		if cond(sibling):
			return sibling
		sibling = sibling.find_next_sibling()
	return None

def get_uma_teams():
	teams_page = load_page("https://umamusu.wiki/Teams_and_Clubs")
	uma_teams = {}

	for h2 in teams_page.find_all("h2"):
		span = h2.find("span", class_="mw-headline")
		if not span or not span.get_text(strip=True).startswith("Team "):
			continue

		team_name = span.get_text(strip=True)[len("Team "):].strip()

		members_div = find_next_sibling(h2, lambda tag: tag.name == "div")
		if not members_div:
			continue

		for box in members_div.find_all("div", class_="icon-box", recursive=False):
			capt = box.find("div", class_="capt-box", recursive=False)
			if not capt:
				continue

			a = capt.find("a")
			if not (a and a.get("title")):
				continue

			name = a.get("title")

			if name not in uma_teams:
				uma_teams[name] = []
			uma_teams[name].append(team_name)

	return uma_teams

def get_uma_game_id():
	with open ("uma_game_ids.json", "r", encoding="utf-8") as f:
		data = json.load(f)
	return data

def get_character_links():
	url = BASE_URL + "/List_of_Characters"
	soup = load_page(url)

	span = soup.find("span", {"id": "Umamusume"})
	if not span:
		return []
	
	h2 = span.find_parent("h2")
	if not h2:
		return []
	
	umamusume_div = h2.find_next_sibling("div")
	if not umamusume_div:
		return []

	links = []
	
	for box in umamusume_div.find_all("div", class_="icon-box", recursive=False):
		capt = box.find("div", class_="capt-box", recursive=False)
		if not capt:
			continue

		a = capt.find("a")
		if not a:
			continue

		links.append(a)
	
	return links

def extract_images(soup, folder_name):
	section = soup.find("section", class_="tabber__section")
	if not section:
		return
	
	for article in section.find_all("article", recursive=False):
		first_a = article.find("a")
		if not first_a:
			continue
		
		subpage = load_page(BASE_URL + first_a.get("href"))
		original_file = subpage.find("a", string="Original file")
		if not original_file:
			continue
		
		img_url = BASE_URL + original_file.get("href")
		img_name = os.path.join(folder_name, os.path.basename(img_url))
		download_img(img_url, img_name)

def extract_attributes(soup):
	table = soup.find("table", class_="infobox")
	if not table:
		return {}

	tbody = table.find("tbody")
	if not tbody:
		return {}
	
	attributes = {}

	for tr in tbody.find_all("tr", recursive=False):
		tds = tr.find_all("td", recursive=False)
		if len(tds) != 2:
			continue

		key_tag = tds[0].find("i")
		if not key_tag:
			continue
		
		value_td = tds[1]
		key = key_tag.get_text(strip=True)
		value = value_td.decode_contents()

		if key in ATTRIBUTES:
			map_value = ATTRIBUTES[key] or (lambda x: x.strip())
			attributes[key] = map_value(value)
	
	return attributes

def scrap_uma(href, uma_name):
	folder_name = os.path.join(OUT_FOLDER, f"+{uma_name.replace("/", "-")}+")
	os.makedirs(folder_name , exist_ok=True)
	
	page = load_page(BASE_URL + href)

	extract_images(page, folder_name)

	attributes = extract_attributes(page)

	title_th = page.find("th", class_="infobox-subheader")
	if title_th:
		i_tag = title_th.find("i")
		if i_tag:
			title = i_tag.get_text(strip=True).replace('"', '')
			attributes["Title"] = title

	if "Dorm" in attributes:
		if attributes["Dorm"] not in DORMS:
			del attributes["Dorm"]

	attributes_path = os.path.join(folder_name, "attributes.json")

	return attributes_path, attributes

def main():
	load_cache()

	os.makedirs(OUT_FOLDER, exist_ok=True)

	uma_teams = get_uma_teams()
	game_ids = get_uma_game_id()

	for a in get_character_links():
		href = a.get("href")
		uma = a.get_text(strip=True)

		attributes_path, attributes = scrap_uma(href, uma)
		
		teams = uma_teams.get(uma, [])
		if teams:
			attributes["Teams"] = ", ".join(teams)

		game_id = game_ids.get(uma, None)
		if game_id:
			attributes["Game ID"] = game_id

		with open(attributes_path, "w", encoding="utf-8") as f:
			json.dump(attributes, f, ensure_ascii=False, indent=4)

	save_cache()

if __name__ == "__main__":
	main()