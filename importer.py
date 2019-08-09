#pip install requests
#pip install patool
#pip install python-dotenv
from pathlib import Path
import requests
import json
import re
import string
import glob
import os
import patoolib
import shutil
import urllib.parse
import functools
import io
import sys
import gzip
import base64
from operator import itemgetter
from dotenv import load_dotenv
load_dotenv()

tags = ['NF', 'DUBBED', '2160p', 'PAL', 'REQ', '18+', 'DVDR', 
		'HEVC', 'NTSC', '480p', '720p', '1080p', 'x264', 'DUAL', 
		'x265', 'BluRay', 'HDTV', 'CAM', 'MP4', 'AAC', 'XviD', 'HDrip', 
		'WEB-DL', 'DD2 0', 'HQ', 'DD5 1', 'DDP5 1', 'H 264', 'AAC2 0', 
		'WEBRiP', 'PDTV', 'PROPER', 'HDTS', 'READNFO', '3D', 'Half-SBS', 
		'SBS', 'DTS', 'AC3', 'INTERNAL', 'MULTi', 'REPACK', 'BDRIP', 
		'DVDRIP', 'AMZN', 'RERiP', 'BRRip', 'LIMITED', 'COMPLETE', 'H264', 'WEB']
os_username = os.getenv("OS_USERNAME")
os_password = os.getenv("OS_PASSWORD")
os_useragent = os.getenv("OS_USERAGENT")
os_token = ''
destinations = {
	'movie': os.getenv('MOVIE_DIRECTORY'),
	'tvshow': os.getenv('TV_SHOW_DIRECTORY')
}
cleansed = []
unpacked = False

data_folder = Path(destinations['movie'])

# Convert folders to Path 
for key in destinations.keys() :
	if destinations.get(key) is not None:
		destinations[key] = Path(destinations.get(key))

def opensubtitles(action, params = []):
	headers = {
    	'User-Agent': os_useragent,
	}

	switcher = {
		'login': {
			'url' : 'https://rest.opensubtitles.org/auth',
			'json' : 1,
			'headers' : headers,
			'stream' : 0
		},
		'search': {
			'url' : 'https://rest.opensubtitles.org/search/' + '/'.join(params),
			'json' : 1,
			'headers' : headers,
			'stream' : 0
		},
		'download': {
			'url' : '/'.join(params),
			'json' : 0,
			'headers' : headers,
			'stream' : 1
		}
	}

	response = requests.get(switcher.get(action)['url'], headers=headers, auth=(os_username, os_password), stream=switcher.get(action)['stream'])

	return response.json() if (switcher.get(action)['json']) else response.raw

def clean_title(title):
	original_title = title
	title_tags = []
	episode = year = ''
	type = 'movie'

	title = title.replace('.', ' ')
	title = re.sub(r'[^A-Za-z0-9 -]', r'', title)

	for tag in tags:
		reg = r'\b' + tag + r'\b'

		if re.search(reg, title, re.IGNORECASE):
			title_tags.append(tag.strip())
			title = re.sub(reg, r'', title, flags=re.I)

	pos = title.find('-')

	if pos >= 0:
		title = title[0:pos]

	# Parse episode
	matches = re.findall(r'\b(S\d{2}E\d{2,3}|S\d{2})\b', title, re.IGNORECASE)

	if len(matches):
		episode = matches[0].strip()
		title = title.replace(episode, '').strip()

	# Parse year
	matches = re.findall(r'\b(\(?\d{4}\)?)+', title, re.IGNORECASE)

	if len(matches):
		year = matches[0].strip()
		title = title.replace(year, '').strip()

	# what does this do
	title = re.sub(r'(?<=(?<!\\pL)\\pL) (?=\\pL(?!\\pL))', r'', title)

	# remove double spaces
	title = re.sub(' +', ' ', title)
	title = string.capwords(title)

	filename = title + (len(episode) and " " + episode or '') + (len(year) and " (" + year + ")" or "")

	if len(episode) > 0 : 
		type = 'tvshow'

	print('Cleaned title {:s} to {:s}'.format(original_title, filename))

	return {
		'title': title,
		'year': year,
		'episode': episode,
		'filename': filename,
		'tags': title_tags,
		'type': type
	}

def unpack_torrent():
	global unpacked
	
	for rarfile in download.glob('*.rar'):
		unpacked = True
		print(str(rarfile))
		print("Unpacking {} files to {}".format(rarfile, download))
		patoolib.extract_archive(str(rarfile), outdir=str(download), verbosity=-1, interactive=False)

	# for fname in os.listdir(download):
	# 	if fname.endswith('.rar'):
	# 		unpacked = True
	# 		print("Unpacking rar files to {:s}".format(download))
	# 		patoolib.extract_archive(download + fname, outdir=download, verbosity=-1)

def move_torrent():
	# print(download)

	for videofile in download.glob('*.mkv'):
		outfile = Path(destination / cleansed['filename']).with_suffix(".mkv")

		if(outfile.exists()):
			print("Deleted old file")
			outfile.unlink()

		shutil.copyfile(videofile, outfile)
		print("Copying {} to {}".format(videofile, outfile))

		if unpacked:
			print("Deleted extracted file")
			videofile.chmod(0o777)
			videofile.unlink()
			# print("Moving {} to {}".format(videofile, outfile))
			# shutil.move(videofile, outfile, copy_function=shutil.copyfile)
		break

def select_subtitles():

	subtitles = opensubtitles('search', {'query-' + urllib.parse.quote(cleansed['filename']), 'sublanguageid-eng' })

	download = []

	for subtitle in subtitles: 

		based_on_torrent = clean_title(subtitle['MovieReleaseName'])

		if(based_on_torrent['title'] != cleansed['title']):
			print('Weird naming')
			continue

        # Check for 100% match on tags
		if (based_on_torrent['tags']==cleansed['tags']):
			download.append({
				'count': 100,
				'subtitle': subtitle
			})
			continue
        
		torrent_source_tags = functools.reduce(set.intersection, map (set, [['BluRay', 'BRRip', 'HDRip', 'WEB-DL', 'BDRip'], cleansed['tags']]))

		if not len(functools.reduce(set.intersection, map (set, [torrent_source_tags, based_on_torrent['tags']]))):
			continue

		torrent_quality_tags = functools.reduce(set.intersection, map (set, [['720p', '1080p', 'x264', 'H264', 'x265', 'HVEC'], cleansed['tags']]))
		
		if not len(functools.reduce(set.intersection, map (set, [torrent_quality_tags, based_on_torrent['tags']]))):
			continue

		download.append({
			'count': len(functools.reduce(set.intersection, map (set, [cleansed['tags'], based_on_torrent['tags']]))),
			'subtitle': subtitle
		})

	download = sorted(download, key=itemgetter('count'))[0:5]

	print('Found {:d} subtitles for download'.format(len(download)))

	return download

if len(sys.argv) == 1:
	print("Download directory missing")
	exit()

download = Path(str(sys.argv[1]))

if download.is_dir() == False:
	print("Download directory {} not found".format(download))
	exit()

# What torrent did we download
torrent = os.path.basename(download)

# Clean the name 
cleansed = clean_title(torrent)

# Set the destination Path
destination = destinations.get(cleansed['type'])

if destination is None:
	print("No destination set found for {:s}".format(cleansed['type']))
	exit()
	
if not destination.is_dir():
	print("Destination directory {} not found".format(destination))
	exit()
		
if cleansed['type'] == "tvshow":
	destination = Path(destination / cleansed['title'])
	if not destination.is_dir():
		destination.mkdir()

# get the token
os_token = opensubtitles('login')['session_id']

# unpack the torrent if needed
unpack_torrent()

# move the torrent to previously defined directory
move_torrent()

downloads = select_subtitles()

for idx, download in enumerate(downloads):
	download_url = download['subtitle']['SubDownloadLink']

	subtitle_file = cleansed['filename'] + '.en' + str(idx > 0 and idx or '') + '.' + download['subtitle']['SubFormat']
	filead_pos = download_url.find('/file')
	download_url = download_url[:filead_pos] + '/sid-' + os_token + download_url[filead_pos:] 
	
	# download subtitle
	downloaded_subtitle = opensubtitles('download', [download_url])

	with open(destination / subtitle_file, 'wb') as f:
		f.write(gzip.GzipFile(fileobj=io.BytesIO(downloaded_subtitle.read())).read())
		f.close()

	print("Downloaded subtitle {:s}".format(download['subtitle']['SubFileName']))

print('Downloaded {:d} subtitles'.format(len(downloads)))
