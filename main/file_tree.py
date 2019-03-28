import attr, base64, collections, flask, hashlib, humanfriendly, json, \
    multiprocessing.pool, os.path, pickle, re, tempfile, threading
from . import app

@attr.s(frozen=True)
class Item:
    id = attr.ib(validator=attr.validators.instance_of(str))
    name = attr.ib(validator=attr.validators.instance_of(str))
    size = attr.ib(validator=attr.validators.instance_of(int))
    url = attr.ib(validator=attr.validators.instance_of(str))
    parent_id = attr.ib(validator=attr.validators.instance_of(str))
    parent_path = attr.ib(validator=attr.validators.instance_of(str))

@attr.s(frozen=True)
class File(Item):
    mime_type = attr.ib(validator=attr.validators.instance_of(str))
    # This is a dictionary of strings. The keys are hash types as given by the
    # API (e.g. 'sha1Hash' from OneDrive). The values are the hash values as
    # given by the API (e.g. a hex string from OneDrive). The values themselves
    # must be hashable.
    hashes = attr.ib(factory=dict)

@attr.s(frozen=True)
class Folder(Item):
    child_count = attr.ib(validator=attr.validators.instance_of(int))

class JSONEncoder(json.JSONEncoder):
    '''
    Helps encode the above types into JSON.
    '''
    _RE_SNAKE = re.compile("_([a-z])")
    @staticmethod
    def _camel(match):
        return match.group(1).upper()
    def default(self, obj):
        if isinstance(obj, Item):
            # Convert the object to a dictionary.
            d = attr.asdict(obj)
            # Convert from snake case to camel case.
            keys = [
                (key_old, self._RE_SNAKE.sub(self._camel, key_old))
                for key_old in d
            ]
            for key_old, key_new in keys:
                d[key_new] = d.pop(key_old)
            return d
        return super().default(obj)

class DuplicateFileScan:
    class NoSuchSave(Exception): pass
    def __init__(self, hash_type, child_yielder, folder_url_getter):
        '''
        Scans for files that have the same hash. You must call step()
        repeatedly until complete is True. The stepped nature of the scan
        allows the scan to be saved via the save() method and resumed later via
        the load() method. After initializing the object, call add_folder_url()
        to add the first folder to scan.
        
        Arguments:
            hash_type:
                the hash type as given by the API (e.g. 'sha1Hash' or
                'quickXorHash' from OneDrive)
            child_yielder:
                a callback function:
                    Arguments:
                        1. a folder URL
                        2. this object's add_folder_url method
                    Returns:
                        generator of Folder and File objects that represent the
                        specified folder's children
            folder_url_getter:
                a function that, given the id attribute from a Folder object,
                returns a full URL that will be passed to child_yielder
        '''
        self._lock = threading.Lock()
        self._child_yielder = child_yielder
        self._folder_url_getter = folder_url_getter
        self._hash_type = hash_type
        self._num_discovered_folders = 0
        self._num_scanned_files = 0
        self._total_bytes_scanned_files = 0
        self._folder_urls_to_scan = collections.deque()
        self._files_with_hash = collections.defaultdict(list)
    def add_folder_url(self, folder_url):
        '''
        Adds a folder to the scan.
        
        Arguments:
            folder_url:
                a URL that can be passed to child_yielder
        '''
        with self._lock:
            self._folder_urls_to_scan.append(folder_url)
    def save(self, token):
        '''
        Saves the current scan for retrieval later. Note that child_yielder
        won't be preserved, so it must be passed back to load() later.
        
        Arguments:
            token: a unique token for this scan
        '''
        # Stash some members temporarily.
        child_yielder = self._child_yielder
        self._child_yielder = None
        folder_url_getter = self._folder_url_getter
        self._folder_url_getter = None
        lock = self._lock
        self._lock = None
        # Save the pickle.
        with open(self._token_to_filename(token), "wb") as f:
            pickle.dump(self, f)
        # Restore the members.
        self._child_yielder = child_yielder
        self._folder_url_getter = folder_url_getter
        self._lock = lock
    @classmethod
    def load(cls, token, child_yielder, folder_url_getter):
        '''
        Retrieves a scan that was saved via the save() method.
        
        Arguments:
            token:
                the unique token that was passed to save()
            child_yielder:
                the same function that was passed as child_yielder to
                __init__()
            folder_url_getter:
                the same function that was passed as folder_url_getter to
                __init__()
        '''
        try:
            f = open(cls._token_to_filename(token), "rb")
        except FileNotFoundError:
            raise cls.NoSuchSave
        with f:
            self = pickle.load(f)
        self._child_yielder = child_yielder
        self._folder_url_getter = folder_url_getter
        self._lock = threading.Lock()
        return self
    @property
    def hash_type(self):
        return self._hash_type
    @property
    def num_scanned_files(self):
        return self._num_scanned_files
    @property
    def num_discovered_folders(self):
        return self._num_discovered_folders
    @property
    def total_bytes_scanned_files(self):
        return self._total_bytes_scanned_files
    @property
    def complete(self):
        return len(self._folder_urls_to_scan) == 0
    def step(self):
        '''
        Performs a step in the scan. The amount of work that is done in one
        step is not specified. If complete is True, nothing will be done.
        '''
        session_pickle = pickle.dumps(dict(flask.session))
        def process_next_folder():
            with app.test_request_context():
                flask.session.update(pickle.loads(session_pickle))
                # Process the next folder in the queue.
                try:
                    with self._lock:
                        next_id = self._folder_urls_to_scan.popleft()
                except IndexError:
                    return True
                self._process_folder_children(
                    self._child_yielder(next_id, self.add_folder_url)
                )
                return False
        with multiprocessing.pool.ThreadPool(16) as pool:
            # Process 32 folders.
            workers = [
                pool.apply_async(process_next_folder, ())
                for _ in range(32)
            ]
            # Wait for them to finish.
            for worker in workers:
                worker.get()
    def get_duplicates(self):
        '''
        Yields lists of File objects. In each list, all the File objects have
        the same hash. Until complete is True, these results will be
        incomplete.
        '''
        # Only yield groups that have more than one member.
        for file_list in self._files_with_hash.values():
            if len(file_list) >= 2:
                yield file_list
    def __str__(self):
        return "Duplicate File Scan using {!r} ({}): " \
            "{} folders discovered, {} files scanned totaling {}".format(
                self.hash_type,
                "complete" if self.complete else "incomplete",
                self.num_discovered_folders,
                self.num_scanned_files,
                humanfriendly.format_size(
                    self.total_bytes_scanned_files,
                    binary=True
                )
            )
    def _process_file(self, file):
        with self._lock:
            self._num_scanned_files += 1
            self._total_bytes_scanned_files += file.size
        # Add this file to the list of files with the same hash.
        hash = file.hashes.get(self._hash_type)
        with self._lock:
            self._files_with_hash[hash].append(file)
    def _process_folder_children(self, child_generator):
        '''
        Arguments:
            child_generator:
                a generator of File and Folder objects that represent the
                files and subfolders in one folder
        '''
        for child in child_generator:
            if isinstance(child, Folder):
                with self._lock:
                    self._num_discovered_folders += 1
                # Only add this folder to the queue if it has children.
                if child.child_count > 0:
                    self.add_folder_url(self._folder_url_getter(child.id))
            elif isinstance(child, File):
                self._process_file(child)
            else:
                raise TypeError("Unknown type", type(child))
    @staticmethod
    def _token_to_filename(token):
        # Hash the token.
        hash = hashlib.sha256()
        hash.update(pickle.dumps(token))
        filename = \
            base64.b32encode(hash.digest()).decode("UTF-8").replace("=", "_")
        # Use the hash in the filename.
        return os.path.join(
            tempfile.gettempdir(),
            "file_tree_dfs-" + filename + ".pickle"
        )
