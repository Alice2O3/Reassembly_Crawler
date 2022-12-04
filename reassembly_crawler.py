import random
import time
import click
import os
import gzip
import urllib
import shutil
import requests
import re
from urllib.parse import unquote
from urllib.parse import quote
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from multiprocessing.dummy import Pool as ThreadPool
import subprocess

class Reassembly_Crawler:
	#static variables and methods
	default_encoding = 'utf-8'
	default_url = 'https://www.anisopteragames.com/sync/pages/'
	support_gzip_suffix = {
		'.lua.gz' : '.lua.gz'
	}
	support_image_suffix = {
		'.jpg' : '.jpg',
		'.JPG' : '.jpg',
		'.png' : '.png'
	}
	image_suffix_check = {
		'.jpg' : b'\xff\xd9',
		'.png' : b'\xaeB`\x82'
	}

	@staticmethod
	def url_unquote(url):
		return unquote(url, encoding=Reassembly_Crawler.default_encoding)

	def url_quote(url):
		return quote(url, encoding=Reassembly_Crawler.default_encoding)
	
	#proxies and headers
	listening_port = 7890
	using_proxies = {
		'https': f'http://127.0.0.1:{listening_port}',
		'http': f'http://127.0.0.1:{listening_port}'
	}
	proxies = None
	headers = {
		'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
	}
	payload = None
	#args
	log_file = os.path.abspath('log.txt')
	log_stream = None
	other_file = os.path.abspath('download_manually.txt')
	other_file_stream = None

	global_url = 'https://www.anisopteragames.com'
	root_url = 'https://www.anisopteragames.com/sync/pages/'

	max_retries = 8
	loading_timeout = 30    #Seconds
	request_timeout = 360
	read_timeout = 1200
	
	#local files
	html_name = 'all_links.html'
	html_file = None
	link_name = 'all_links.txt'
	link_file = None
	download_dir_rel = 'download'
	download_dir = None
	flattened_file_rel = 'flattened.txt'
	flattened_file = None

	#find abnormal urls
	not_found_file_rel = '404.txt'
	not_found_file = None
	not_found_file_html_rel = '404_html.txt'
	not_found_file_html = None
	not_found_urls = {}
	not_found_htmls = {}

	#session and thread pool
	session = None
	thread_pool = None
	pool_size = 128
	move_pool_size = 16
	global_map_set = {}

	#regular expressions
	regex_data = re.compile(r'^(.*)_([0-9]+_[0-9]+\.[0-9]+\.[0-9]+)_([0-9]+)PM?\.lua\.gz$')
	regex_data_processed = re.compile(r'^([0-9]+)P_(.*)_([0-9]+_[0-9]+\.[0-9]+\.[0-9]+)\.lua\.gz$')

	#find file lists
	file_index = {}
	file_list_P = []
	P_group = {
		'0-500P' 	 : (0   , 500),
		'501-1000P'  : (501 , 1000),
		'1001-1500P' : (1001, 1500),
		'1501-2000P' : (1501, 2000),
		'2001-2500P' : (2001, 2500),
		'2501-3000P' : (2501, 3000),
		'3001-3500P' : (3001, 3500),
		'3501-4000P' : (3501, 4000),
		'4001-4500P' : (4001, 4500),
		'4501-5000P' : (4501, 5000),
		'5001-5500P' : (5001, 5500),
		'5501-6000P' : (5501, 6000),
		'6001-6500P' : (6001, 6500),
		'6501-7000P' : (6501, 7000),
		'7001-7500P' : (7001, 7500),
		'7501-8000P' : (7501, 8000),
		'8000+P'     : (8001, 2147483647)
	}
	P_group_dir = {}
	file_list_P_grouped = {}

	#kwargs
	input_dir = None
	output_dir = None
	download_num = None
	crawler_mode = None
	waiting_time = None
	check_update = None
	grouped = None
	#Stable: Check images after each download 
	#Quick: Quickly download all images, no repair
	#ImageFix: Only check and fix the images in the dictionary

	def __init__(self, input_dir, output_dir, download_num, crawler_mode, waiting_time, check_update, grouped):
		self.log_stream = open(self.log_file, 'wb')
		self.input_dir = os.path.abspath(input_dir)
		self.output_dir = os.path.abspath(output_dir)
		self.crawler_mode = crawler_mode
		self.waiting_time = waiting_time	#Seconds
		self.html_file = os.path.join(self.input_dir, self.html_name)
		self.link_file = os.path.join(self.input_dir, self.link_name)
		self.download_dir = os.path.join(self.input_dir, self.download_dir_rel)
		self.flattened_file = os.path.join(self.input_dir, self.flattened_file_rel)
		self.not_found_file = os.path.join(self.input_dir, self.not_found_file_rel)
		self.not_found_file_html = os.path.join(self.input_dir, self.not_found_file_html_rel)
		self.download_num = download_num
		self.check_update = check_update
		self.grouped = grouped
		#Timing
		self.start_time = 0
		self.finish_time = 0

	def write_to_stream(self, string, file_stream, flush = True):
		file_stream.write((string + '\n').encode(Reassembly_Crawler.default_encoding))
		if flush:
			file_stream.flush()

	def show_message(self, string, write_to_log = False):
		print(string, flush=True)
		if write_to_log:
			self.write_to_stream(string, self.log_stream)

	#Directory operations
	def mkdir(self, dir):
		os.makedirs(dir, exist_ok=True)

	def remove_dir_recursive(self, dir):
		if not os.path.exists(dir):
			return
		shutil.rmtree(path=dir)

	def walk_dir(self, dirname): #Generator
		for root, dirs, files in os.walk(dirname):
			for f in files:
				yield (os.path.join(root, f), root, f)

	def copy_function(self, src, dst, *, follow_symlinks=True):
		self.show_message(f"Copying {src} to {dst}")
		if os.path.isdir(dst):
			dst = os.path.join(dst, os.path.basename(src))
		shutil.copyfile(src, dst, follow_symlinks=follow_symlinks)
		shutil.copymode(src, dst, follow_symlinks=follow_symlinks)
		return dst

	#String operations
	def remove_suffix(self, string, suffix):
		if string.endswith(suffix):
			return string[:-len(suffix)]
		return string

	def remove_suffix_uncheck(self, string, suffix):
		return string[:-len(suffix)]

	def extract_dir_name(self, url):
		root = url.split('/')
		if not root[-1]:
			return root[-2]
		return None

	def extract_file_name(self, url):
		return url.split('/')[-1]

	def file_broken(self, file_path):
		if not os.path.exists(file_path):
			return True
		if os.path.getsize(file_path) < 2:
			return True
		#jpg ending: buf.endswith(b'\xff\xd9'), png ending: buf.endswith(b'\xaeB`\x82')
		for suffix in self.support_gzip_suffix.keys():
			if file_path.endswith(suffix):
				try:
					z = gzip.open(file_path, 'rb')
					return False
				except Exception as e:
					return True
				finally:
					z.close()
		for suffix, eof in self.image_suffix_check.items():
			if file_path.endswith(suffix):
				with open(file_path, 'rb') as f:
					f.seek(-2, 2)
					buf = f.read()
				if buf.endswith(eof):
					return False
		return True

	def scan_list(self, broken_list):
		for file_name, file_url in broken_list:
			self.show_message(file_name, True)

	def scan_delete(self, broken_list):
		for file_name, file_url in broken_list:
			os.remove(file_name)

	def write_data(self, res, file_name):
		#self.show_message(res)
		with open(file_name, 'wb') as f:
			shutil.copyfileobj(res.raw, f)
			res.close()

	#Request functions
	def get_response_session(self, url, session, payload = None, method = 'get', stream = False, err_callback = lambda: None):
		try:
			if method == 'get':
				res = session.get(url, headers = self.headers, data = payload, stream = stream,
				timeout = (self.request_timeout, self.read_timeout), proxies=self.proxies)
			if method == 'post':
				res = session.post(url, headers = self.headers, data = payload, stream = stream,
				timeout = (self.request_timeout, self.read_timeout), proxies = self.proxies)
		except requests.exceptions.RequestException as e:
			self.show_message(f'[ERROR] Request Expception: {e}', True)
			return None
		except requests.exceptions.Timeout as e:
			self.show_message(f'[ERROR] Connect Timeout: {e}', True)
			return None
		except requests.exceptions.ConnectionError as e:
			self.show_message(f'[ERROR] Read Timeout: {e}', True)
			return None
		else:
			if res.status_code != 200:
				self.show_message(f'Url {url} not found!', True)
				err_callback()
				return res
			return res

	def get_response_file(self, file_url):
		def record_notfound_url():
			self.not_found_urls[file_url] = True
		with requests.Session() as session:
			return self.get_response_session(file_url, session, payload = self.payload, 
				stream = True, err_callback = record_notfound_url)

	def check_connection(self):
		try:
			res = self.session.get(self.global_url, headers=self.headers, 
				timeout=self.loading_timeout, proxies=self.proxies)
		except requests.exceptions.RequestException as e:
			return False
		except requests.exceptions.Timeout as e:
			return False
		except requests.exceptions.ConnectionError as e:
			return False
		else:
			if res.status_code != 200:
				return False
			return True

	#Save functions
	def save_attempt(self, file_url, file_name):
		if os.path.exists(file_name):
			#self.show_message(f'File {file_name} already exists!')
			if self.file_broken(file_name):
				self.show_message(f'File {file_name} is broken, redownloading...')
			else:
				return False
		self.show_message(f'Downloading {file_url}...')
		it = 0
		while True:
			res = self.get_response_file(file_url)
			if not res:
				return False
			self.write_data(res, file_name)
			if self.file_broken(file_name):
				self.show_message(f'File {file_name} is broken, redownloading...', True)
				self.show_message(f'Retrying({it}/{self.max_retries})...', True)
				it += 1
				if it >= self.max_retries:
					self.show_message(f'[ERROR] Exceeding max retries({self.max_retries})!', True)
					return False
			else:
				return True

	def save_attempt_quick(self, file_url, file_name):
		if os.path.exists(file_name):
			#self.show_message(f'File {file_name} already exists!')
			if self.file_broken(file_name):
				self.show_message(f'File {file_name} is broken, redownloading...')
			else:
				return False
		return self.save_attempt_fix(file_url, file_name)

	def save_attempt_fix(self, file_url, file_name):
		self.show_message(f'Downloading {file_url}...')
		res = self.get_response_file(file_url)
		if not res:
			return False
		self.write_data(res, file_name)
		if self.file_broken(file_name):
			self.show_message(f'File {file_name} is broken, ignoring...')
			return False
		return True

	def save_file(self, file_url, file_name, file_input_func):
		if file_input_func(file_url, file_name): # Whether to show the message
			self.show_message(f'[SUCCESS] File {file_url} successfully saved to {file_name}')

	#File Fix
	def file_fix_list(self, broken_list):
		self.multi_thread_file(broken_list, file_input_func = self.save_attempt_fix)
		return self.file_fix_check(broken_list)

	def file_fix_check(self, iterable):
		file_count, broken_count = 0, 0
		broken_list = []
		self.show_message('[NOTICE] Checking downloaded files...', True)
		for file_name, file_url in iterable:
			if self.file_broken(file_name):
				broken_count += 1
				broken_list.append((file_name, file_url))
			file_count += 1
		self.show_message(f'{file_count} files collected, {broken_count} broken:', True)
		self.scan_list(broken_list)
		return broken_list

	def file_fix_path(self, root_path):
		broken_list = []
		for file_name, root, f in self.walk_dir(self.output_dir):
			if file_name in self.file_index:
				broken_list.append((file_name, self.file_index[file_name]))
		broken_list = self.file_fix_check(broken_list)
		it = 0
		while broken_list:
			temp_list = self.file_fix_list(broken_list)
			if len(temp_list) == len(broken_list):
				it += 1
				self.show_message(f'No file downloaded')
				self.show_message(f'Retrying ({it}/{self.max_retries})...')
			else:
				broken_list = temp_list
				it = 0
			if it >= self.max_retries:
				self.show_message(f'[ERROR] Exceeding max retries ({self.max_retries})!', True)
				break
		return broken_list

	def file_fix(self):
		broken_list = self.file_fix_path(self.output_dir)
		self.show_message('[NOTICE] File Fix complete!', True)
		if broken_list:
			self.show_message('Error Files:', True)
			#Scan and delete error images
			self.scan_list(broken_list)
			if self.remove_error_images:
				self.scan_delete(broken_list)
		else:
			self.show_message('No Error Files!', True)

	# Main functions
	def start_program(self):
		self.session = requests.Session()
		self.start_program_dry()

	def end_program(self):
		self.end_program_dry()
		self.session.close()

	def start_program_dry(self):
		self.start_time = time.time()
		self.show_message('[START] Session Start', True)
		self.show_message(f'[NOTICE] Crawler is now running at {self.crawler_mode} Mode', True)

	def end_program_dry(self):
		self.finish_time = time.time()
		self.show_message(f'[END] Program Finished in {(self.finish_time - self.start_time):.2f}s', True)
		self.log_stream.close()

	def check_directory(self):
		if not os.path.exists(self.input_dir):
			self.show_message('[ERROR] Input directory not found!', True)
			return False
		if not os.path.exists(self.flattened_file):
			self.show_message('[ERROR] Link file not found!', True)
			return False
		return True

	def set_proxies(self):
		self.proxies = self.using_proxies
		if self.check_connection():
			self.show_message('[NOTICE] Using proxies...', True)
		else:
			self.proxies = None
			if not self.check_connection():
				self.show_message('[ERROR] No Connection!', True)
				return False
		self.show_message(f'[NOTICE] Connected to {self.global_url}', True)
		return True

	#Xml Paraser
	def save_to_local(self, root_url):
		if self.check_update:
			self.show_message(f'[NOTICE] Checking Update...', True)
		elif os.path.isfile(self.html_file):
			self.show_message(f'[NOTICE] {self.html_file} already exists!', True)
			return
		else:
			self.show_message(f'[NOTICE] {self.html_file} does not exist, downloading...', True)
		res = self.get_response_session(self.root_url, self.session, self.payload)
		with open(self.html_file, 'wb') as f:
			self.write_to_stream(res.text, f)
	
	def collect_hrefs(self, soup, hrefs):
		for label in soup.find_all('a'):
			if label.has_attr('href'):
				hrefs.append(urljoin(self.root_url, label['href']))

	def get_all_links(self):
		if self.check_update:
			self.show_message(f'[NOTICE] Updating {self.link_file}...', True)
		elif os.path.isfile(self.link_file):
			self.show_message(f'[NOTICE] {self.link_file} already exists!', True)
			return
		else:
			self.show_message(f'[NOTICE] {self.link_file} does not exist, downloading...', True)
		html_file = open(self.html_file, 'r', encoding = Reassembly_Crawler.default_encoding)
		soup = BeautifulSoup(html_file.read(), 'html.parser')
		hrefs = []
		self.collect_hrefs(soup, hrefs)
		#self.show_message(hrefs)
		num_users = 0
		with open(self.link_file, 'wb') as f:
			for url in hrefs:
				if url.endswith('.html'):
					self.write_to_stream(url, f)
					num_users += 1
		self.show_message(f'Number of users: {num_users}')

	def split_file(self, file_path):
		with open(file_path, 'rb') as input_stream:
			return input_stream.read().decode(Reassembly_Crawler.default_encoding).splitlines()

	def get_download_links(self):
		self.mkdir(self.download_dir)
		self.multi_thread(self.get_links_from_url, self.split_file(self.link_file), self.pool_size)
		self.show_message(f'[NOTICE] Get links complete!', True)

	def get_download_links_local(self):
		self.show_message(f'[NOTICE] Collected files is at {self.download_dir}', True)
		file_num = 0
		with open(self.flattened_file, 'wb') as output_stream:
			for file_path, root, f in self.walk_dir(self.download_dir):
				for url in self.split_file(file_path):
					self.write_to_stream(url, output_stream)
					file_num += 1
		self.show_message(f'[NOTICE] All urls saved to {self.flattened_file}!', True)
		self.show_message(f'[NOTICE] {file_num} urls collected.', True)

	#Get Download Links
	def url_check_suffix(self, link):
		for suffix in self.support_gzip_suffix.keys():
			if link.endswith(suffix):
				return True
		return False

	def get_links_from_url(self, url):
		if url in self.not_found_htmls.keys():
			self.show_message(f'[NOTICE] {url} is broken, skipping', True)
			return
		self.show_message(f'Processing {url}')
		raw_file_name = os.path.join(self.download_dir, 
			self.remove_suffix_uncheck(url.split('/')[-1], '.html'))
		file_name = Reassembly_Crawler.url_unquote(raw_file_name) + '.txt'
		if os.path.exists(file_name):
			self.show_message(f'[NOTICE] {url} already retrieved, skipping')
			return
		res = None
		it = 0
		while True:
			res = self.get_response_session(url, self.session)
			if res:
				break
			self.show_message(f'[ERROR] Error processing {url}, retrying ({it}/{self.max_retries})...', True)
			it += 1
			if it >= self.max_retries:
				self.show_message(f'[ERROR] Exceeding max retries!', True)
				self.not_found_htmls[url] = True
				return
		soup = BeautifulSoup(res.text, 'html.parser')
		#self.show_message(soup.prettify())
		hrefs = []
		self.collect_hrefs(soup, hrefs)
		download_list = []
		for rel_link in hrefs:
			if self.url_check_suffix(rel_link):
				abs_link = urljoin(url, rel_link)
				self.show_message(f'Retrieved: {abs_link}')
				download_list.append(abs_link)
		#Disable flush and put all data at once to avoid data corruption
		with open(file_name, 'wb') as output_stream:
			for abs_link in download_list:
				self.write_to_stream(abs_link, output_stream, flush = False)

	#Multi Thread
	def multi_thread(self, input_func, tuple_list, pool_size):
		self.thread_pool = ThreadPool(pool_size)
		random.shuffle(tuple_list)
		self.thread_pool.map(input_func, tuple_list)
		self.thread_pool.close()
		self.thread_pool.join()

	def delay(self):
		if self.waiting_time > 0:
			time.sleep(self.waiting_time)

	def multi_thread_file(self, path_tuples, file_input_func):
		def task(path_tuple):
			file_name, file_url = path_tuple
			self.save_file(file_url, file_name, file_input_func = file_input_func)
			self.delay()
		self.multi_thread(task, path_tuples, self.pool_size)

	#Data parsing
	def extract_data(self, file_name, regex):
		return re.search(regex, file_name).groups()

	def data_in_group(self, kpoint, group):
		l, r = group
		return l <= kpoint and kpoint <= r

	def get_group_name(self, kpoint):
		knum = int(kpoint)
		for group_name, group in self.P_group.items():
			if self.data_in_group(knum, group):
				return group_name

	#Create file index
	def get_download_list(self):
		raw_data = self.split_file(self.flattened_file)
		if self.download_num:
			return random.sample(raw_data, self.download_num)
		return raw_data

	#Generate file names
	def generate_file_name(self, url):
		name, date, kpoint = self.extract_data(url.split('/')[-1], self.regex_data)
		return os.path.join(self.output_dir, f'{kpoint}P_{name}_{date}.lua.gz')

	def generate_file_name_grouped(self, url):
		name, date, kpoint = self.extract_data(url.split('/')[-1], self.regex_data)
		group_name = self.get_group_name(kpoint)
		return os.path.join(self.P_group_dir[group_name], f'{kpoint}P_{name}_{date}.lua.gz')

	def generate_file_name_local(self, file_name):
		return os.path.join(self.output_dir, file_name)

	def generate_file_name_grouped_local(self, file_name):
		kpoint, name, date = self.extract_data(file_name, self.regex_data_processed)
		group_name = self.get_group_name(kpoint)
		return os.path.join(self.P_group_dir[group_name], f'{kpoint}P_{name}_{date}.lua.gz')

	def create_file_index(self):
		#Create file index
		self.show_message(f'[NOTICE] Create file index...', True)
		for url in self.get_download_list():
			if url in self.not_found_urls.keys():
				self.show_message(f'{url} not found, skipping...')
				continue
			self.file_index[self.generate_file_name(url)] = url

	def create_grouped_dir(self):
		#Create group directories
		for group_name in self.P_group.keys():
			group_dir = os.path.join(self.output_dir, group_name)
			self.P_group_dir[group_name] = group_dir
			self.mkdir(group_dir)

	def create_file_index_grouped(self):
		self.create_grouped_dir()
		#Create file index
		self.show_message(f'[NOTICE] Create file index...', True)
		for url in self.get_download_list():
			if url in self.not_found_urls.keys():
				self.show_message(f'{url} not found, skipping...')
				continue
			self.file_index[self.generate_file_name_grouped(url)] = url

	#Also keep tracking of not found urls for next use
	def not_found_urls_in(self, not_found_file, not_found_urls):
		if not os.path.exists(not_found_file):
			self.show_message(f'[NOTICE] File {not_found_file} not found, skipping...', True)
			return
		self.show_message(f'[NOTICE] Reading broken urls from {not_found_file}...', True)
		for file_url in self.split_file(not_found_file):
			not_found_urls[file_url] = True

	def not_found_urls_out(self, not_found_file, not_found_urls):
		self.show_message(f'[NOTICE] Writing broken urls to {not_found_file}...', True)
		with open(not_found_file, 'wb') as output_stream:
			for file_url in not_found_urls.keys():
				self.write_to_stream(file_url, output_stream)

	#Main APIs
	def download_files(self, file_input_func):
		self.show_message(f'[NOTICE] Downloading files...', True)
		self.multi_thread_file(list(self.file_index.items()), file_input_func = file_input_func)
		self.show_message(f'[NOTICE] All files downloaded!', True)

	def execute(self):
		self.start_program()
		#Checking proxies
		if not self.set_proxies():
			self.end_program()
			return False
		#Create input directory
		self.mkdir(self.input_dir)
		#Get links
		if self.crawler_mode == 'GetLinks':
			self.not_found_urls_in(self.not_found_file_html, self.not_found_htmls)
			self.save_to_local(self.root_url)
			self.get_all_links()
			self.get_download_links()
			self.get_download_links_local()
			self.not_found_urls_out(self.not_found_file_html, self.not_found_htmls)
			self.end_program()
			return True
		#Check directory
		if not self.check_directory():
			self.show_message(f'[ERROR] Error checking directory', True)
			self.end_program()
			return False
		#Process not found urls
		self.not_found_urls_in(self.not_found_file, self.not_found_urls)
		#Create output directory
		self.mkdir(self.output_dir)
		#Create file index
		if self.grouped:
			self.create_file_index_grouped()
		else:
			self.create_file_index()
		#Download files
		if self.crawler_mode == 'Fix':
			self.file_fix()
		if self.crawler_mode == 'Stable':
			self.download_files(self.save_attempt)
		if self.crawler_mode == 'Quick':
			self.download_files(self.save_attempt_quick)
		#Process not found urls
		self.not_found_urls_out(self.not_found_file, self.not_found_urls)
		#Calculate Time
		self.end_program()
		return True

	#Post Processing
	def post_processing(self):
		self.start_program()
		self.show_message(f'[NOTICE] Post processing')
		#Create directories
		self.mkdir(self.output_dir)
		if self.grouped:
			self.create_grouped_dir()
		#Generate raw data
		raw_data = []
		new_path_func = None
		if self.grouped:
			new_path_func = self.generate_file_name_grouped_local
		else:
			new_path_func = self.generate_file_name_local
		for file_path, root, f in self.walk_dir(self.input_dir):
			new_path = new_path_func(f)
			if os.path.exists(new_path):
				self.show_message(f'{new_path} exists, skipping')
				continue
			raw_data.append((file_path, new_path))
		#Random sample
		if self.download_num:
			copy_list = random.sample(raw_data, self.download_num)
		else:
			copy_list = raw_data
		#Copy files
		for file_path, new_path in copy_list:
			self.show_message(f'Copying {file_path} -> {new_path}')
			shutil.copy(file_path, new_path)
		#End program
		self.show_message(f'[NOTICE] Post processing finished')
		self.end_program()

	def debug(self):
		self.show_message(Reassembly_Crawler.url_unquote(self.root_url))

#TODO: grouped
@click.command()
@click.option('--input_dir', help = 'Input directory', type = str, required = True)
@click.option('--output_dir', help = 'Output directory', type = str, required = True)
@click.option('--download_num', help = 'Number of files to download', type = click.IntRange(min = 1), required = False)
@click.option('--crawler_mode', help = 'Crawler Mode', type = click.Choice(['Stable', 'Quick', 'Fix', 'GetLinks']), default = 'Stable', show_default = True)
@click.option('--waiting_time', help = 'Waiting time after each batch (Unit: Second)', type = click.FloatRange(min = 0), default = 1, show_default = True)
@click.option('--check_update', help = 'Whether to check update of the website', is_flag = True)
@click.option('--grouped', help = 'Group data by P value while downloading', is_flag = True)
@click.option('--post_processing', help = 'Post processing mode', is_flag = True)
def crawler(input_dir, 
	output_dir, 
	download_num, 
	crawler_mode, 
	waiting_time, 
	check_update, 
	grouped, 
	post_processing
):
	spider = Reassembly_Crawler(input_dir,
		output_dir,
		download_num,
		crawler_mode,
		waiting_time,
		check_update,
		grouped
	)
	if post_processing:
		spider.post_processing()
		return
	spider.execute()
	#spider.debug()

if __name__ == '__main__':
	crawler() # pylint: disable=no-value-for-parameter
