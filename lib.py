# -*- coding: utf-8 -*-
from __future__ import unicode_literals  # support both Python2 and 3

""" lib.py

PyOTRS lib

This code implements the PyOTRS library to provide access to the OTRS API (REST)
"""

import os
import io
import base64
import mimetypes
import json
import time
import datetime
import requests
import logging

log = logging.getLogger(__name__)

TICKET_CONNECTOR_CONFIG_DEFAULT = {
    'Name': 'KomandConnectorREST',
    'Config': {
        'SessionCreate': {'RequestMethod': 'POST',
                          'Route': '/Session',
                          'Result': 'SessionID'},
        'TicketCreate': {'RequestMethod': 'POST',
                         'Route': '/Ticket',
                         'Result': 'TicketID'},
        'TicketGet': {'RequestMethod': 'GET',
                      'Route': '/Ticket/:TicketID',
                      'Result': 'Ticket'},
        'TicketGetList': {'RequestMethod': 'GET',
                          'Route': '/TicketList',
                          'Result': 'Ticket'},
        'TicketSearch': {'RequestMethod': 'GET',
                         'Route': '/Search',
                         'Result': 'TicketID'},
        'TicketUpdate': {'RequestMethod': 'PATCH',
                         'Route': '/Update/:TicketID',
                         'Result': 'TicketID'},
    }
}

FAQ_CONNECTOR_CONFIG_DEFAULT = {
    'Name': 'GenericFAQConnectorREST',
    'Config': {
        'LanguageList': {'RequestMethod': 'GET',
                         'Route': '/LanguageList',
                         'Result': 'Language'},
        'PublicCategoryList': {'RequestMethod': 'GET',
                               'Route': '/PublicCategoryList',
                               'Result': 'Category'},
        'PublicFAQGet': {'RequestMethod': 'GET',
                         'Route': '/PublicFAQGet',
                         'Result': 'FAQItem'},
        'PublicFAQSearch': {'RequestMethod': 'POST',
                            'Route': '/PublicFAQSearch',
                            'Result': 'ID'},
    }
}

LINK_CONNECTOR_CONFIG_DEFAULT = {
    'Name': 'GenericLinkConnectorREST',
    'Config': {
        'LinkAdd': {'RequestMethod': 'POST',
                    'Route': '/LinkAdd',
                    'Result': 'LinkAdd'},
        'LinkDelete': {'RequestMethod': 'DELETE',
                       'Route': '/LinkDelete',
                       'Result': 'LinkDelete'},
        'LinkDeleteAll': {'RequestMethod': 'DELETE',
                          'Route': '/LinkDeleteAll',
                          'Result': 'LinkDeleteAll'},
        'LinkList': {'RequestMethod': 'GET',
                     'Route': '/LinkList',
                     'Result': 'LinkList'},
        'PossibleLinkList': {'RequestMethod': 'GET',
                             'Route': '/PossibleLinkList',
                             'Result': 'PossibleLinkList'},
        'PossibleObjectsList': {'RequestMethod': 'GET',
                                'Route': '/PossibleObjectsList',
                                'Result': 'PossibleObject'},
        'PossibleTypesList': {'RequestMethod': 'GET',
                              'Route': '/PossibleTypesList',
                              'Result': 'PossibleType'},
    }
}


class PyOTRSError(Exception):
    def __init__(self, message):
        super(PyOTRSError, self).__init__(message)
        self.message = message


class ArgumentMissingError(PyOTRSError):
    pass


class ArgumentInvalidError(PyOTRSError):
    pass


class ResponseParseError(PyOTRSError):
    pass


class SessionCreateError(PyOTRSError):
    pass


class SessionNotCreated(PyOTRSError):
    pass


class APIError(PyOTRSError):
    pass


class HTTPError(PyOTRSError):
    pass


class Article(object):
    """PyOTRS Article class """
    def __init__(self, dct):
        fields = {}
        for key, value in dct.items():
            fields.update({key: dct[key]})

        try:
            self.aid = int(fields.get("ArticleID"))
        except TypeError:
            self.aid = 0

        self.fields = fields

        self.attachments = self._parse_attachments()
        self.fields.pop("Attachment", None)

        self.dynamic_fields = self._parse_dynamic_fields()
        self.fields.pop("DynamicField", None)

    def __repr__(self):
        if self.aid is not 0:
            _len = len(self.attachments)
            if _len == 0:
                return "<ArticleID: {1}>".format(self.__class__.__name__, self.aid)
            elif _len == 1:
                return "<ArticleID: {1} (1 Attachment)>".format(self.__class__.__name__,
                                                                self.aid)
            else:
                return "<ArticleID: {1} ({2} Attachments)>".format(self.__class__.__name__,
                                                                   self.aid, _len)
        else:
            return "<{0}>".format(self.__class__.__name__)

    def to_dct(self, attachments=True, attachment_cont=True, dynamic_fields=True):
        """represent as nested dict compatible for OTRS

        Args:
            attachments (bool): if True will include, otherwise exclude:
                "Attachment" (default: True)
            attachment_cont (bool): if True will include, otherwise exclude:
                "Attachment" > "Content" (default: True)
            dynamic_fields (bool): if True will include, otherwise exclude:
                "DynamicField" (default: True)

        Returns:
            **dict**: Article represented as dict for OTRS

        """
        dct = {}

        if attachments:
            if self.attachments:
                dct.update({"Attachment": [x.to_dct(content=attachment_cont) for x in
                                           self.attachments]})

        if dynamic_fields:
            if self.dynamic_fields:
                dct.update({"DynamicField": [x.to_dct() for x in self.dynamic_fields]})

        if self.fields:
            dct.update(self.fields)

        return dct

    def _parse_attachments(self):
        """parse Attachment from Ticket and return as **list** of **Attachment** objects"""
        lst = self.fields.get("Attachment")
        if lst:
            return [Attachment(item) for item in lst]
        else:
            return []

    def _parse_dynamic_fields(self):
        """parse DynamicField from Ticket and return as **list** of **DynamicField** objects"""
        lst = self.fields.get("DynamicField")
        if lst:
            return [DynamicField.from_dct(item) for item in lst]
        else:
            return []

    def attachment_get(self, a_filename):
        """attachment_get

        Args:
            a_filename (str): Filename of Attachment to retrieve

        Returns:
            **Attachment** or **None**

        """
        result = [x for x in self.attachments if x.Filename == "{0}".format(a_filename)]
        if result:
            return result[0]
        else:
            return None

    def dynamic_field_get(self, df_name):
        """dynamic_field_get

        Args:
            df_name (str): Name of DynamicField to retrieve

        Returns:
            **DynamicField** or **None**

        """

        result = [x for x in self.dynamic_fields if x.name == "{0}".format(df_name)]
        if result:
            return result[0]
        else:
            return None

    def field_get(self, f_name):
        return self.fields.get(f_name)

    def validate(self, validation_map=None):
        """validate data against a mapping dict - if a key is not present
        then set it with a default value according to dict

        Args:
            validation_map (dict): A mapping for all Article fields that have to be set. During
            validation every required field that is not set will be set to a default value
            specified in this dict.

        .. note::
            There is also a blacklist (fields to be removed) but this is currently
            hardcoded to *dynamic_fields* and *attachments*.

        """
        if not validation_map:
            validation_map = {"Body": "API created Article Body",
                              "Charset": "UTF8",
                              "MimeType": "text/plain",
                              "Subject": "API created Article",
                              "TimeUnit": 0}

        for key, value in validation_map.items():
            if not self.fields.get(key, None):
                self.fields.update({key: value})

    @classmethod
    def _dummy(cls):
        """dummy data (for testing)

        Returns:
            **Article**: An Article object.

        """
        return Article({"Subject": "Dümmy Subject",
                        "Body": "Hallo Bjørn,\n[kt]\n\n -- The End",
                        "TimeUnit": 0,
                        "MimeType": "text/plain",
                        "Charset": "UTF8"})

    @classmethod
    def _dummy_force_notify(cls):
        """dummy data (for testing)

        Returns:
            **Article**: An Article object.

        """
        return Article({"Subject": "Dümmy Subject",
                        "Body": "Hallo Bjørn,\n[kt]\n\n -- The End",
                        "TimeUnit": 0,
                        "MimeType": "text/plain",
                        "Charset": "UTF8",
                        "ForceNotificationToUserID": [1, 2]})


class Attachment(object):
    """PyOTRS Attachment class """
    def __init__(self, dct):
        self.__dict__ = dct

    def __repr__(self):
        if hasattr(self, 'Filename'):
            return "<{0}: {1}>".format(self.__class__.__name__, self.Filename)
        else:
            return "<{0}>".format(self.__class__.__name__)

    def to_dct(self, content=True):
        """represent Attachment object as dict
        Args:
            content (bool): if True will include, otherwise exclude: "Content" (default: True)

        Returns:
            **dict**: Attachment represented as dict.

        """
        dct = self.__dict__
        if content:
            return dct
        else:
            dct.pop("Content")
            return dct

    @classmethod
    def create_basic(cls, Content=None, ContentType=None, Filename=None):
        """create a basic Attachment object

        Args:
            Content (str): base64 encoded content
            ContentType (str): MIME type of content (e.g. text/plain)
            Filename (str): file name (e.g. file.txt)


        Returns:
            **Attachment**: An Attachment object.

        """
        return Attachment({'Content': Content,
                           'ContentType': ContentType,
                           'Filename': Filename})

    @classmethod
    def create_from_file(cls, file_path):
        """save Attachment to a folder on disc

        Args:
            file_path (str): The full path to the file from which an Attachment should be created.

        Returns:
            **Attachment**: An Attachment object.

        """
        with io.open(file_path, 'rb') as f:
            content = f.read()

        content_type = mimetypes.guess_type(file_path)[0]
        if not content_type:
            content_type = "application/octet-stream"
        return Attachment({'Content': base64.b64encode(content),
                           'ContentType': content_type,
                           'Filename': os.path.basename(file_path)})

    def save_to_dir(self, folder="/tmp"):
        """save Attachment to a folder on disc

        Args:
            folder (str): The directory where this attachment should be saved to.

        Returns:
            **bool**: True

        """
        if not hasattr(self, 'Content') or not hasattr(self, 'Filename'):
            raise ValueError("invalid Attachment")

        file_path = os.path.join(os.path.abspath(folder), self.Filename)
        with open(file_path, 'wb') as f:
            f.write(base64.b64decode(self.Content))

        return True

    @classmethod
    def _dummy(cls):
        """dummy data (for testing)

        Returns:
            **Attachment**: An Attachment object.

        """
        return Attachment.create_basic("YmFyCg==", "text/plain", "dümmy.txt")


class DynamicField(object):
    """PyOTRS DynamicField class

    Args:
        name (str): Name of OTRS DynamicField (required)
        value (str): Value of OTRS DynamicField
        search_operator (str): Search operator (defaults to: "Equals")
            Valid options are:
            "Equals", "Like", "GreaterThan", "GreaterThanEquals",
            "SmallerThan", "SmallerThanEquals"
        search_patterns (list): List of patterns (str or datetime) to search for

    .. warning::
        **PyOTRS only supports OTRS 5 style!**
        DynamicField representation changed between OTRS 4 and OTRS 5.

    """

    SEARCH_OPERATORS = ("Equals", "Like", "GreaterThan", "GreaterThanEquals",
                        "SmallerThan", "SmallerThanEquals",)

    def __init__(self, name, value=None, search_patterns=None, search_operator="Equals"):
        self.name = name
        self.value = value

        if not isinstance(search_patterns, list):
            self.search_patterns = [search_patterns]
        else:
            self.search_patterns = search_patterns

        if search_operator not in DynamicField.SEARCH_OPERATORS:
            raise NotImplementedError("Invalid Operator: \"{0}\"".format(search_operator))
        self.search_operator = search_operator

    def __repr__(self):
        return "<{0}: {1}: {2}>".format(self.__class__.__name__, self.name, self.value)

    @classmethod
    def from_dct(cls, dct):
        """create DynamicField from dct

        Args:
            dct (dict):

        Returns:
            **DynamicField**: A DynamicField object.

        """
        return cls(name=dct["Name"], value=dct["Value"])

    def to_dct(self):
        """represent DynamicField as dict

        Returns:
            **dict**: DynamicField as dict.

        """
        return {"Name": self.name, "Value": self.value}

    def to_dct_search(self):
        """represent DynamicField as dict for search operations

        Returns:
            **dict**: DynamicField as dict for search operations

        """
        _lst = []
        for item in self.search_patterns:
            if isinstance(item, datetime.datetime):
                item = item.strftime("%Y-%m-%d %H:%M:%S")
            _lst.append(item)

        return {"DynamicField_{0}".format(self.name): {self.search_operator: _lst}}

    @classmethod
    def _dummy1(cls):
        """dummy1 data (for testing)

        Returns:
            **DynamicField**: A list of DynamicField objects.

        """
        return DynamicField(name="firstname", value="Jane")

    @classmethod
    def _dummy2(cls):
        """dummy2 data (for testing)

        Returns:
            **DynamicField**: A list of DynamicField objects.

        """
        return DynamicField.from_dct({'Name': 'lastname', 'Value': 'Doe'})


class Ticket(object):
    """PyOTRS Ticket class

        Args:
           tid (int): OTRS Ticket ID as integer
           fields (dict): OTRS Top Level fields
           articles (list): List of Article objects
           dynamic_fields (list): List of DynamicField objects

    """
    def __init__(self, dct):
        # store OTRS Top Level fields
        self.fields = {}
        self.fields.update(dct)

        self.tid = int(self.fields.get("TicketID", 0))
        self.articles = self._parse_articles()
        self.fields.pop("Article", None)

        self.dynamic_fields = self._parse_dynamic_fields()
        self.fields.pop("DynamicField", None)

    def __repr__(self):
        if self.tid:
            return "<{0}: {1}>".format(self.__class__.__name__, self.tid)
        else:
            return "<{0}>".format(self.__class__.__name__)

    def _parse_articles(self):
        """parse Article from Ticket and return as **list** of **Article** objects"""
        lst = self.fields.get("Article", [])
        return [Article(item) for item in lst]

    def _parse_dynamic_fields(self):
        """parse DynamicField from Ticket and return as **list** of **DynamicField** objects"""
        lst = self.fields.get("DynamicField", [])
        return [DynamicField.from_dct(item) for item in lst]

    def to_dct(self,
               articles=True,
               article_attachments=True,
               article_attachment_cont=True,
               article_dynamic_fields=True,
               dynamic_fields=True):
        """represent as nested dict

        Args:
            articles (bool): if True will include, otherwise exclude:
                "Article" (default: True)
            article_attachments (bool): if True will include, otherwise exclude:
                "Article" > "Attachment" (default: True)
            article_attachment_cont (bool): if True will include, otherwise exclude:
                "Article" > "Attachment" > "Content" (default: True)
            article_dynamic_fields (bool): if True will include, otherwise exclude:
                "Article" > "DynamicField" (default: True)
            dynamic_fields (bool): if True will include, otherwise exclude:
                "DynamicField" (default: True)

        Returns:
            **dict**: Ticket represented as dict.

        .. note::
            Does not contain Articles or DynamicFields (currently)

        """
        dct = {}
        dct.update(self.fields)

        if articles:
            try:
                if self.articles:
                    dct.update({"Article": [x.to_dct(attachments=article_attachments,
                                                     attachment_cont=article_attachment_cont,
                                                     dynamic_fields=article_dynamic_fields)
                                            for x in self.articles]})
            except AttributeError:
                pass

        if dynamic_fields:
            try:
                if self.dynamic_fields:
                    dct.update({"DynamicField": [x.to_dct() for x in self.dynamic_fields]})
            except AttributeError:
                pass

        return {"Ticket": dct}

    def article_get(self, aid):
        """article_get

        Args:
            aid (str): Article ID as either int or str

        Returns:
            **Article** or **None**

        """
        result = [x for x in self.articles if x.field_get("ArticleID") == str(aid)]
        return result[0] if result else None

    def dynamic_field_get(self, df_name):
        """dynamic_field_get

        Args:
            df_name (str): Name of DynamicField to retrieve

        Returns:
            **DynamicField** or **None**

        """
        result = [x for x in self.dynamic_fields if x.name == df_name]
        return result[0] if result else None

    def field_get(self, f_name):
        return self.fields.get(f_name)

    @classmethod
    def create_basic(cls,
                     Title=None,
                     QueueID=None,
                     Queue=None,
                     TypeID=None,
                     Type=None,
                     StateID=None,
                     State=None,
                     PriorityID=None,
                     Priority=None,
                     CustomerUser=None):
        """create basic ticket

        Args:
            Title (str): OTRS Ticket Title
            QueueID (str): OTRS Ticket QueueID (e.g. "1")
            Queue (str): OTRS Ticket Queue (e.g. "raw")
            TypeID (str): OTRS Ticket TypeID (e.g. "1")
            Type (str): OTRS Ticket Type (e.g. "Problem")
            StateID (str): OTRS Ticket StateID (e.g. "1")
            State (str): OTRS Ticket State (e.g. "open" or "new")
            PriorityID (str): OTRS Ticket PriorityID (e.g. "1")
            Priority (str): OTRS Ticket Priority (e.g. "low")
            CustomerUser (str): OTRS Ticket CustomerUser

        Returns:
            **Ticket**: A new Ticket object.

        """
        if not Title:
            raise ArgumentMissingError("Title is required")

        if not Queue and not QueueID:
            raise ArgumentMissingError("Either Queue or QueueID required")

        if not State and not StateID:
            raise ArgumentMissingError("Either State or StateID required")

        if not Priority and not PriorityID:
            raise ArgumentMissingError("Either Priority or PriorityID required")

        if not CustomerUser:
            raise ArgumentMissingError("CustomerUser is required")

        if Type and TypeID:
            raise ArgumentInvalidError("Either Type or TypeID - not both")

        dct = {u"Title": Title}

        if Queue:
            dct.update({"Queue": Queue})
        else:
            dct.update({"QueueID": QueueID})

        if Type:
            dct.update({"Type": Type})
        if TypeID:
            dct.update({"TypeID": TypeID})

        if State:
            dct.update({"State": State})
        else:
            dct.update({"StateID": StateID})

        if Priority:
            dct.update({"Priority": Priority})
        else:
            dct.update({"PriorityID": PriorityID})

        dct.update({"CustomerUser": CustomerUser})

        for key, value in dct.items():
            dct.update({key: value})

        return Ticket(dct)

    @classmethod
    def _dummy(cls):
        """dummy data (for testing)

        Returns:
            **Ticket**: A Ticket object.

        """
        return Ticket.create_basic(Queue=u"Raw",
                                   State=u"open",
                                   Priority=u"3 normal",
                                   CustomerUser="root@localhost",
                                   Title="Bäsic Ticket")

    @staticmethod
    def datetime_to_pending_time_text(datetime_object=None):
        """datetime_to_pending_time_text

        Args:
            datetime_object (Datetime)

        Returns:
            **str**: The pending time in the format required for OTRS REST interface.

        """
        return {
            "Year": datetime_object.year,
            "Month": datetime_object.month,
            "Day": datetime_object.day,
            "Hour": datetime_object.hour,
            "Minute": datetime_object.minute
        }


class SessionStore(object):
    """Session ID: persistently store to and retrieve from to file

    Args:
        file_path (str): Path on disc
        session_timeout (int): OTRS Session Timeout Value (to avoid reusing outdated session id
        value (str): A Session ID as str
        created (int): seconds as epoch when a session_id record was created
        expires (int): seconds as epoch when a session_id record expires

    Raises:
        ArgumentMissingError

    """
    def __init__(self, file_path=None, session_timeout=None,
                 value=None, created=None, expires=None):
        if not file_path:
            raise ArgumentMissingError("Argument file_path is required!")

        if not session_timeout:
            raise ArgumentMissingError("Argument session_timeout is required!")

        self.file_path = file_path
        self.timeout = session_timeout
        self.value = value
        self.created = created
        self.expires = expires

    def __repr__(self):
        return "<{0}: {1}>".format(self.__class__.__name__, self.file_path)

    def read(self):
        """Retrieve a stored Session ID from file

        Returns:
            **str** or **None**: Retrieved Session ID or None (if none could be read)

        """
        if not os.path.isfile(self.file_path):
            return None

        if not SessionStore._validate_file_owner_and_permissions(self.file_path):
            return None

        with open(self.file_path, "r") as f:
            content = f.read()
        try:
            data = json.loads(content)
            self.value = data['session_id']

            self.created = datetime.datetime.utcfromtimestamp(int(data['created']))
            self.expires = (self.created +
                            datetime.timedelta(minutes=self.timeout))

            if self.expires > datetime.datetime.utcnow():
                return self.value  # still valid
        except ValueError:
            return None
        except KeyError:
            return None
        except Exception as err:
            raise Exception("Exception Type: {0}: {1}".format(type(err), err))

    def write(self, new_value):
        """Write and store a Session ID to file (rw for user only)

        Args:
            new_value (str): if none then empty value will be writen to file
        Returns:
            **bool**: **True** if successful, False **otherwise**.

        """
        self.value = new_value

        if os.path.isfile(self.file_path):
            if not SessionStore._validate_file_owner_and_permissions(self.file_path):
                raise IOError("File exists but is not ok (wrong owner/permissions)!")

        with open(self.file_path, 'w') as f:
            f.write(json.dumps({'created': str(int(time.time())),
                                'session_id': self.value}))
        os.chmod(self.file_path, 384)  # 384 is '0600'

        # TODO 2016-04-23 (RH): check this
        if not SessionStore._validate_file_owner_and_permissions(self.file_path):
            raise IOError("Race condition: Something happened to file during the run!")

        return True

    def delete(self):
        """remove session id file (e.g. when it only contains an invalid session id

        Raises:
            NotImplementedError

        Returns:
            **bool**: **True** if successful, otherwise **False**.

        .. todo::
            (RH) implement this _remove_session_id_file
        """
        raise NotImplementedError("Not yet done")

    @staticmethod
    def _validate_file_owner_and_permissions(full_file_path):
        """validate SessionStore file ownership and permissions

        Args:
            full_file_path (str): full path to file on disc

        Returns:
            **bool**: **True** if valid and correct, otherwise **False**...

        """
        if not os.path.isfile(full_file_path):
            raise IOError("Does not exist or not a file: {0}".format(full_file_path))

        file_lstat = os.lstat(full_file_path)
        if not file_lstat.st_uid == os.getuid():
            return False

        if not file_lstat.st_mode & 0o777 == 384:
            """ check for unix permission User R+W only (0600)
            >>> oct(384)
            '0600' Python 2
            >>> oct(384)
            '0o600'  Python 3  """
            return False

        return True


class Client(object):
    """PyOTRS Client class - includes Session handling

    Args:
        baseurl (str): Base URL for OTRS System, no trailing slash e.g. http://otrs.example.com
        username (str): Username
        password (str): Password
        session_id_file (str): Session ID path on disc, used to persistently store Session ID
        session_timeout (int): Session Timeout configured in OTRS (usually 28800 seconds = 8h)
        session_validation_ticket_id (int): Ticket ID of an existing ticket - used to perform
            several check - e.g. validate log in (defaults to 1)
        webservice_config_ticket (dict): OTRS REST Web Service Name - Ticket Connector
        webservice_config_faq (dict): OTRS REST Web Service Name - FAQ Connector
        webservice_config_link (dict): OTRS REST Web Service Name - Link Connector
        proxies (dict): Proxy settings - refer to requests docs for
            more information - default to no proxies
        https_verify (bool): Should HTTPS certificates be verified (defaults to True)
        ca_cert_bundle (str): file path - if specified overrides python/system default for
            Root CA bundle that will be used.
        user_agent (str): optional HTTP UserAgent string
        webservice_path (str): OTRS REST Web Service Path part - defaults to
            "/otrs/nph-genericinterface.pl/Webservice/"

    """
    def __init__(self,
                 baseurl=None,
                 username=None,
                 password=None,
                 session_id_file=None,
                 session_timeout=None,
                 session_validation_ticket_id=1,
                 webservice_config_ticket=None,
                 webservice_config_faq=None,
                 webservice_config_link=None,
                 proxies=None,
                 https_verify=True,
                 ca_cert_bundle=None,
                 user_agent=None,
                 webservice_path="/otrs/nph-genericinterface.pl/Webservice/"):

        if not baseurl:
            raise ArgumentMissingError("baseurl")
        self.baseurl = baseurl.rstrip("/")
        self.webservice_path = webservice_path

        if not session_timeout:
            self.session_timeout = 28800  # 8 hours is OTRS default
        else:
            self.session_timeout = session_timeout

        if not session_id_file:
            self.session_id_store = SessionStore(file_path="/tmp/.pyotrs_session_id",
                                                 session_timeout=self.session_timeout)
        else:
            self.session_id_store = SessionStore(file_path=session_id_file,
                                                 session_timeout=self.session_timeout)

        self.session_validation_ticket_id = session_validation_ticket_id

        # A dictionary for mapping OTRS WebService operations to HTTP Method, Route and
        # Result string.
        if not webservice_config_ticket:
            webservice_config_ticket = TICKET_CONNECTOR_CONFIG_DEFAULT

        if not webservice_config_faq:
            webservice_config_faq = FAQ_CONNECTOR_CONFIG_DEFAULT

        if not webservice_config_link:
            webservice_config_link = LINK_CONNECTOR_CONFIG_DEFAULT

        self.ws_ticket = TICKET_CONNECTOR_CONFIG_DEFAULT['Name']
        self.ws_faq = FAQ_CONNECTOR_CONFIG_DEFAULT['Name']
        self.ws_link = LINK_CONNECTOR_CONFIG_DEFAULT['Name']

        self.routes_ticket = [x[1]["Route"] for x in webservice_config_ticket['Config'].items()]
        self.routes_faq = [x[1]["Route"] for x in webservice_config_faq['Config'].items()]
        self.routes_link = [x[1]["Route"] for x in webservice_config_link['Config'].items()]

        webservice_config = {}
        webservice_config.update(webservice_config_ticket['Config'])
        webservice_config.update(webservice_config_faq['Config'])
        webservice_config.update(webservice_config_link['Config'])
        self.ws_config = webservice_config

        if not proxies:
            self.proxies = {"http": "", "https": "", "no": ""}
        else:
            if not isinstance(proxies, dict):
                raise ValueError("Proxy settings need to be provided as dict!")
            self.proxies = proxies

        if https_verify:
            if not ca_cert_bundle:
                self.https_verify = https_verify
            else:
                ca_certs = os.path.abspath(ca_cert_bundle)
                if not os.path.isfile(ca_certs):
                    raise ValueError("Certificate file does not exist: {0}".format(ca_certs))
                self.https_verify = ca_certs
        else:
            self.https_verify = False

        self.user_agent = user_agent

        # credentials
        self.username = username
        self.password = password

        # dummy initialization
        self.operation = None
        self.result_json = None
        self.result = []

    """
    GenericInterface::Operation::Session::SessionCreate
        * session_check_is_valid
        * session_create
        * session_restore_or_set_up_new  # try to get session_id from a (json) file on disc
    """
    def session_check_is_valid(self, session_id=None):
        """check whether session_id is currently valid

        Args:
            session_id (str): optional If set overrides the self.session_id

        Raises:
            ArgumentMissingError: if session_id is not set

        Returns:
            **bool**: **True** if valid, otherwise **False**.

        .. note::
            Uses HTTP Method: GET
        """
        self.operation = "TicketGet"

        if not session_id:
            raise ArgumentMissingError("session_id")

        # TODO 2016-04-13 (RH): Is there a nicer way to check whether session is valid?!
        payload = {"SessionID": session_id}

        response = self._send_request(payload, ticket_id=self.session_validation_ticket_id)
        return self._parse_and_validate_response(response)

    def session_create(self):
        """create new (temporary) session (and Session ID)

        Returns:
            **bool**: **True** if successful, otherwise **False**.

        .. note::
            Session ID is recorded in self.session_id_store.value (**non persistently**)

        .. note::
            Uses HTTP Method: POST

        """
        self.operation = "SessionCreate"

        payload = {
            "UserLogin": self.username,
            "Password": self.password
        }

        if not self._parse_and_validate_response(self._send_request(payload)):
            return False

        self.session_id_store.value = self.result_json['SessionID']
        return True

    def session_restore_or_set_up_new(self):
        """Try to restore Session ID from file otherwise create new one and save to file

        Raises:
            SessionCreateError
            SessionIDFileError

        .. note::
            Session ID is recorded in self.session_id_store.value (**non persistently**)

        .. note::
            Session ID is **saved persistently** to file: *self.session_id_store.file_path*

        Returns:
            **bool**: **True** if successful, otherwise **False**.
        """
        # try to read session_id from file
        self.session_id_store.value = self.session_id_store.read()

        if self.session_id_store.value:
            # got one.. check whether it's still valid
            try:
                if self.session_check_is_valid(self.session_id_store.value):
                    log.info("Using valid Session ID "
                             "from ({0})".format(self.session_id_store.file_path))
                    return True
            except APIError:
                """most likely invalid session_id so pass. Remove clear session_id_store.."""

        # got no (valid) session_id; clean store
        self.session_id_store.write("")

        # and try to create new one
        if not self.session_create():
            raise SessionCreateError("Failed to create a Session ID!")

        # save new created session_id to file
        if not self.session_id_store.write(self.result_json['SessionID']):
            raise IOError("Failed to save Session ID to file!")
        else:
            log.info("Saved new Session ID to file: "
                     "{0}".format(self.session_id_store.file_path))
            return True

    """
    GenericInterface::Operation::Ticket::TicketCreate
        * ticket_create
    """
    def ticket_create(self,
                      ticket=None,
                      article=None,
                      attachments=None,
                      dynamic_fields=None,
                      **kwargs):
        """Create a Ticket

        Args:
            ticket (Ticket): a ticket object
            article (Article): optional article
            attachments (list): *Attachment* objects
            dynamic_fields (list): *DynamicField* object
            **kwargs: any regular OTRS Fields (not for Dynamic Fields!)

        Returns:
            **dict** or **False**: dict if successful, otherwise **False**.
        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "TicketCreate"

        payload = {"SessionID": self.session_id_store.value}

        if not ticket:
            raise ArgumentMissingError("Ticket")

        if not article:
            raise ArgumentMissingError("Article")

        payload.update(ticket.to_dct())

        if article:
            article.validate()
            payload.update({"Article": article.to_dct()})

        if attachments:
            # noinspection PyTypeChecker
            payload.update({"Attachment": [att.to_dct() for att in attachments]})

        if dynamic_fields:
            # noinspection PyTypeChecker
            payload.update({"DynamicField": [df.to_dct() for df in dynamic_fields]})

        if not self._parse_and_validate_response(self._send_request(payload)):
            return False
        else:
            return self.result_json

    """
    GenericInterface::Operation::Ticket::TicketGet

        * ticket_get_by_id
        * ticket_get_by_list
        * ticket_get_by_number
    """
    def ticket_get_by_id(self,
                         ticket_id,
                         articles=False,
                         attachments=False,
                         dynamic_fields=True,
                         html_body_as_attachment=False):
        """ticket_get_by_id

        Args:
            ticket_id (int): Integer value of a Ticket ID
            attachments (bool): will request OTRS to include attachments (*default: False*)
            articles (bool): will request OTRS to include all
                    Articles (*default: False*)
            dynamic_fields (bool): will request OTRS to include all
                    Dynamic Fields (*default: True*)
            html_body_as_attachment (bool): Optional, If enabled the HTML body version of
                    each article is added to the attachments list

        Returns:
            **Ticket** or **False**: Ticket object if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "TicketGet"

        payload = {
            "SessionID": self.session_id_store.value,
            "TicketID": "{0}".format(ticket_id),
            "AllArticles": int(articles),
            "Attachments": int(attachments),
            "DynamicFields": int(dynamic_fields),
            "HTMLBodyAsAttachment": int(html_body_as_attachment),
        }

        response = self._send_request(payload, ticket_id)
        if not self._parse_and_validate_response(response):
            return False
        else:
            return self.result[0]

    def ticket_get_by_list(self,
                           ticket_id_list,
                           articles=False,
                           attachments=False,
                           dynamic_fields=True,
                           html_body_as_attachment=False):
        """ticket_get_by_list

        Args:
            ticket_id_list (list): List of either String or Integer values
            attachments (bool): will request OTRS to include attachments (*default: False*)
            articles (bool): will request OTRS to include all
                    Articles (*default: False*)
            dynamic_fields (bool): will request OTRS to include all
                    Dynamic Fields (*default: True*)
            html_body_as_attachment (bool): Optional, If enabled the HTML body version of
                    each article is added to the attachments list

        Returns:
            **list**: Ticket objects (as list) if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "TicketGetList"

        if not isinstance(ticket_id_list, list):
            raise ArgumentInvalidError("Please provide list of IDs!")

        payload = {
            "SessionID": self.session_id_store.value,
            "TicketID": ','.join([str(item) for item in ticket_id_list]),
            "AllArticles": int(articles),
            "Attachments": int(attachments),
            "DynamicFields": int(dynamic_fields),
            "HTMLBodyAsAttachment": int(html_body_as_attachment),
        }

        if not self._parse_and_validate_response(self._send_request(payload)):
            return False
        else:
            return self.result

    def ticket_get_by_number(self,
                             ticket_number,
                             articles=False,
                             attachments=False,
                             dynamic_fields=True,
                             html_body_as_attachment=False):
        """ticket_get_by_number

        Args:
            ticket_number (str): Ticket Number as str
            attachments (bool): will request OTRS to include attachments (*default: False*)
            articles (bool): will request OTRS to include all
                    Articles (*default: False*)
            dynamic_fields (bool): will request OTRS to include all
                    Dynamic Fields (*default: True*)
            html_body_as_attachment (bool): Optional, If enabled the HTML body version of
                    each article is added to the attachments list

        Raises:
            ValueError

        Returns:
            **Ticket** or **False**: Ticket object if successful, otherwise **False**.

        """
        if isinstance(ticket_number, int):
            raise ArgumentInvalidError("Provide ticket_number as str/unicode. "
                                       "Got ticket_number as int.")
        result_list = self.ticket_search(TicketNumber=ticket_number)

        if not result_list:
            return False

        if len(result_list) == 1:
            result = self.ticket_get_by_id(result_list[0],
                                           articles=articles,
                                           attachments=attachments,
                                           dynamic_fields=dynamic_fields,
                                           html_body_as_attachment=html_body_as_attachment)
            if not result:
                return False
            else:
                return result
        else:
            # TODO 2016-11-12 (RH): more than one ticket found for a specific ticket number
            raise ValueError("Found more than one result for "
                             "Ticket Number: {0}".format(ticket_number))

    """
    GenericInterface::Operation::Ticket::TicketSearch
        * ticket_search
        * ticket_search_full_text
    """
    def ticket_search(self, dynamic_fields=None, **kwargs):
        """Search for ticket

        Args:
            dynamic_fields (list): List of DynamicField objects for which the search
                should be performed
            **kwargs: Arbitrary keyword arguments (not for DynamicField objects).

        Returns:
            **list** or **False**: The search result (as list) if successful (can be an
                empty list: []), otherwise **False**.

        .. note::
            If value of kwargs is a datetime object then this object will be
            converted to the appropriate string format for OTRS API.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "TicketSearch"
        payload = {
            "SessionID": self.session_id_store.value,
        }

        if dynamic_fields:
            if isinstance(dynamic_fields, DynamicField):
                payload.update(dynamic_fields.to_dct_search())
            else:
                for df in dynamic_fields:
                    payload.update(df.to_dct_search())

        if kwargs is not None:
            for key, value in kwargs.items():
                if isinstance(value, datetime.datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                payload.update({key: value})

        if not self._parse_and_validate_response(self._send_request(payload)):
            return False
        else:
            return self.result

    def ticket_search_full_text(self, pattern):
        """Wrapper for search ticket for full text search

        Args:
            pattern (str): Search pattern (a '%' will be added to front and end automatically)

        Returns:
            **list** or **False**: The search result (as list) if successful,
                otherwise **False**.

        """
        self.operation = "TicketSearch"
        pattern_wildcard = "%{0}%".format(pattern)

        return self.ticket_search(FullTextIndex="1",
                                  ContentSearch="OR",
                                  Subject=pattern_wildcard,
                                  Body=pattern_wildcard)

    """
    GenericInterface::Operation::Ticket::TicketUpdate
        * ticket_update
        * ticket_update_set_pending
    """
    def ticket_update(self,
                      ticket_id,
                      article=None,
                      attachments=None,
                      dynamic_fields=None,
                      **kwargs):
        """Update a Ticket

        Args:

            ticket_id (int): Ticket ID as integer value
            article (Article): **optional** one *Article* that will be add to the ticket
            attachments (list): list of one or more *Attachment* objects that will
                be added to ticket. Also requires an *Article*!
            dynamic_fields (list): *DynamicField* objects
            **kwargs: any regular Ticket Fields (not for Dynamic Fields!)

        Returns:
            **dict** or **False**: A dict if successful, otherwise **False**.
        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "TicketUpdate"

        payload = {"SessionID": self.session_id_store.value, "TicketID": ticket_id}

        if article:
            article.validate()
            payload.update({"Article": article.to_dct()})

        if attachments:
            if not article:
                raise ArgumentMissingError("To create an attachment an article is needed!")
            # noinspection PyTypeChecker
            payload.update({"Attachment": [att.to_dct() for att in attachments]})

        if dynamic_fields:
            # noinspection PyTypeChecker
            payload.update({"DynamicField": [df.to_dct() for df in dynamic_fields]})

        if kwargs is not None and not kwargs == {}:
            ticket_dct = {}
            for key, value in kwargs.items():
                ticket_dct.update({key: value})
            payload.update({"Ticket": ticket_dct})

        if not self._parse_and_validate_response(self._send_request(payload, ticket_id)):
            return False

        return self.result_json

    def ticket_update_set_pending(self,
                                  ticket_id,
                                  new_state="pending reminder",
                                  pending_days=1,
                                  pending_hours=0):
        """ticket_update_set_state_pending

        Args:
            ticket_id (int): Ticket ID as integer value
            new_state (str): defaults to "pending reminder"
            pending_days (int): defaults to 1
            pending_hours (int): defaults to 0

        Returns:
            **dict** or **False**: A dict if successful, otherwise **False**.

        .. note::
            Operates in UTC
        """
        datetime_now = datetime.datetime.utcnow()
        pending_till = datetime_now + datetime.timedelta(days=pending_days, hours=pending_hours)

        pt = Ticket.datetime_to_pending_time_text(datetime_object=pending_till)

        return self.ticket_update(ticket_id, State=new_state, PendingTime=pt)

    """
    GenericInterface::Operation::FAQ::LanguageList
        * faq_language_list

    """

    def faq_language_list(self):
        """faq_language_list"""
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "LanguageList"

        payload = {
            "SessionID": self.session_id_store.value
        }

        result = self._parse_and_validate_response(self._send_request(payload))
        if result:
            return self.result

    def faq_category_list(self):
        """faq_public_category_list"""
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "PublicCategoryList"

        payload = {
            "SessionID": self.session_id_store.value
        }

        result = self._parse_and_validate_response(self._send_request(payload))
        if result:
            return self.result

    def faq_public_faq_get(self, item_ids=None, attachment_contents=True):
        """faq_public_category_list

        Args:
            item_ids (list): list of item IDs
            attachment_contents (bool): whether to retrieve content of FAQ attachments

        Returns:
            **list**: of **dict** containing FAQ data

        """

        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "PublicFAQGet"

        payload = {
            "SessionID": self.session_id_store.value
        }

        if not item_ids:
            raise ArgumentMissingError("item_ids is required")

        if isinstance(item_ids, list):
            _ids = ",".join([str(x) for x in item_ids])
        else:
            _ids = item_ids

        payload.update({"ItemID": _ids})
        if not attachment_contents:
            payload.update({"GetAttachmentContents": 0})

        if self._parse_and_validate_response(self._send_request(payload)):
            return self.result

    def faq_public_faq_search(self, what=None, number=None, title=None, search_dict=None):
        """faq_public_category_list

        Args:
            what (str):
            number (str):
            title (str):
            search_dict (dict):

        Returns:
            **list**: of found FAQ item IDs

        # Original documentation:
        # perform PublicFAQSearch Operation. This will return a list of public FAQ entries.
        #       Number = > '*134*',              # (optional)
        #       Title = > '*some title*',        # (optional)
        #
        #       # is searching in Number, Title, Keyword and Field1-6
        #       What = > '*some text*',          # (optional)
        #
        #       Keyword = > '*webserver*',       # (optional)
        #       LanguageIDs = > [4, 5, 6],       # (optional)
        #       CategoryIDs = > [7, 8, 9],       # (optional)

        """

        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "PublicFAQSearch"

        payload = {
            "SessionID": self.session_id_store.value,
        }

        if what:
            payload.update({"What": what})

        if number:
            payload.update({"Number": number})

        if title:
            payload.update({"Title": title})

        if search_dict:
            if not isinstance(search_dict, dict):
                raise ArgumentInvalidError("Expecting dict for search_dict!")
            payload.update(search_dict)

        if self._parse_and_validate_response(self._send_request(payload)):
            if not self.result:
                return []
            elif len(self.result) == 1:
                return [self.result]
            else:
                return self.result

    """
    GenericInterface::Operation::Link::LinkAdd
        * link_add
    """
    def link_add(self,
                 src_object_id,
                 dst_object_id,
                 src_object_type="Ticket",
                 dst_object_type="Ticket",
                 link_type="Normal",
                 state="Valid"):
        """link_add

        Args:
            src_object_id (int): Integer value of source object ID
            dst_object_id (int): Integer value of destination object ID
            src_object_type (str): Object type of source; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            dst_object_type (str): Object type of destination; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            link_type (str): Type of the link: "Normal" or "ParentChild" (*default: Normal*)
            state (str): State of the link (*default: Normal*)

        Returns:
            **True** or **False**: True if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "LinkAdd"

        payload = {
            "SessionID": self.session_id_store.value,
            "SourceObject": src_object_type,
            "SourceKey": int(src_object_id),
            "TargetObject": dst_object_type,
            "TargetKey": int(dst_object_id),
            "Type": link_type,
            "State": state
        }

        return self._parse_and_validate_response(self._send_request(payload))

    """
    GenericInterface::Operation::Link::LinkDelete
        * link_delete
    """
    def link_delete(self,
                    src_object_id,
                    dst_object_id,
                    src_object_type="Ticket",
                    dst_object_type="Ticket",
                    link_type="Normal"):
        """link_delete

        Args:
            src_object_id (int): Integer value of source object ID
            src_object_type (str): Object type of source; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            dst_object_id (int): Integer value of source object ID
            dst_object_type (str): Object type of source; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            link_type (str): Type of the link: "Normal" or "ParentChild" (*default: Normal*)

        Returns:
            **True** or **False**: True if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "LinkDelete"

        payload = {
            "SessionID": self.session_id_store.value,
            "Object1": src_object_type,
            "Key1": int(src_object_id),
            "Object2": dst_object_type,
            "Key2": int(dst_object_id),
            "Type": link_type
        }

        return self._parse_and_validate_response(self._send_request(payload))

    """
    GenericInterface::Operation::Link::LinkDeleteAll
        * link_delete_all
    """
    def link_delete_all(self,
                        object_id,
                        object_type="Ticket",):
        """link_delete_all

        Args:
            object_id (int): Integer value of source object ID
            object_type (str): Object type of source; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)

        Returns:
            **True** or **False**: True if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "LinkDeleteAll"

        payload = {
            "SessionID": self.session_id_store.value,
            "Object": object_type,
            "Key": int(object_id)
        }

        return self._parse_and_validate_response(self._send_request(payload))

    """
    GenericInterface::Operation::Link::LinkList
        * link_list
    """
    def link_list(self,
                  src_object_id,
                  src_object_type="Ticket",
                  dst_object_type=None,
                  state="Valid",
                  link_type=None,
                  direction=None):
        """link_list

        Args:
            src_object_id (int): Object type of source; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            src_object_type (str): Object type of destination; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            dst_object_type (str): Object type of destination; e.g. "Ticket", "FAQ"...
                Optional restriction of the object where the links point to. (*default: Ticket*)
            state (str): State of the link (*default: Valid*)
            link_type (str): Type of the link: "Normal" or "ParentChild" (*default: Normal*)
            direction (str): Optional restriction of the link direction ('Source' or 'Target').

        Returns:
            **Dict** or **None**: Dict if successful, if empty **None**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "LinkList"

        payload = {
            "SessionID": self.session_id_store.value,
            "Object": src_object_type,
            "Key": int(src_object_id),
            "State": state
        }

        if dst_object_type:
            payload.update({"Object2": dst_object_type})

        if link_type:
            payload.update({"Type": link_type})

        if direction:
            payload.update({"Direction": direction})

        return self._parse_and_validate_response(self._send_request(payload))

    """
    GenericInterface::Operation::Link::PossibleLinkList
        * link_possible_link_list
    """
    def link_possible_link_list(self):
        """link_possible_link_list

        Returns:
            **List** or **False**: List if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "PossibleLinkList"

        payload = {
            "SessionID": self.session_id_store.value,
        }

        if self._parse_and_validate_response(self._send_request(payload)):
            return self.result
        else:
            return False

    """
    GenericInterface::Operation::Link::PossibleObjectsList
        * link_possible_objects_list
    """
    def link_possible_objects_list(self,
                                   object_type="Ticket"):
        """link_possible_objects_list

        Args:
            object_type (str): Object type; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)

        Returns:
            **List** or **False**: List if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "PossibleObjectsList"

        payload = {
            "SessionID": self.session_id_store.value,
            "Object": object_type,
        }

        if self._parse_and_validate_response(self._send_request(payload)):
            return self.result
        else:
            return False

    """
    GenericInterface::Operation::Link::PossibleTypesList
        * link_possible_types_list
    """
    def link_possible_types_list(self,
                                 src_object_type="Ticket",
                                 dst_object_type="Ticket"):
        """link_possible_types_list

        Args:
            src_object_type (str): Object type of source; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)
            dst_object_type (str): Object type of destination; e.g. "Ticket", "FAQ"...
                (*default: Ticket*)

        Returns:
            **List** or **False**: List if successful, otherwise **False**.

        """
        if not self.session_id_store.value:
            raise SessionNotCreated("Call session_create() or "
                                    "session_restore_or_set_up_new() first")
        self.operation = "PossibleTypesList"

        payload = {
            "SessionID": self.session_id_store.value,
            "Object1": src_object_type,
            "Object2": dst_object_type,
        }

        if self._parse_and_validate_response(self._send_request(payload)):
            return self.result
        else:
            return False

    def _build_url(self, ticket_id=None):
        """build url for request

        Args:
            ticket_id (optional[int])

        Returns:
            **str**: The complete URL where the request will be send to.

        """
        route = self.ws_config[self.operation]["Route"]

        if ":" in route:
            route_split = route.split(":")
            route = route_split[0]
            route_arg = route_split[1]

            if route_arg == "TicketID":
                if not ticket_id:
                    raise ValueError("TicketID is None but Route requires "
                                     "TicketID: {0}".format(route))
                self._url = ("{0}{1}{2}{3}{4}".format(
                    self.baseurl, self.webservice_path, self.ws_ticket, route, ticket_id))
        else:
            if route in self.routes_ticket:
                self._url = ("{0}{1}{2}{3}".format(
                    self.baseurl, self.webservice_path, self.ws_ticket, route))
            elif route in self.routes_faq:
                self._url = ("{0}{1}{2}{3}".format(
                    self.baseurl, self.webservice_path, self.ws_faq, route))
            elif route in self.routes_link:
                self._url = ("{0}{1}{2}{3}".format(
                    self.baseurl, self.webservice_path, self.ws_link, route))

        return self._url

    def _send_request(self, payload=None, ticket_id=None):
        """send the API request using the *requests.request* method

        Args:
            payload (dict)
            ticket_id (optional[dict])

        Raises:
            OTRSHTTPError:

        Returns:
            **requests.Response**: Response received after sending the request.

        .. note::
            Supported HTTP Methods: DELETE, GET, HEAD, PATCH, POST, PUT
        """
        if not payload:
            raise ArgumentMissingError("payload")

        self._result_type = self.ws_config[self.operation]["Result"]

        url = self._build_url(ticket_id)

        http_method = self.ws_config[self.operation]["RequestMethod"]

        if http_method not in ["DELETE", "GET", "HEAD", "PATCH", "POST", "PUT"]:
            raise ValueError("invalid http_method")

        headers = {"Content-Type": "application/json"}

        if self.user_agent:
            headers.update({"User-Agent": self.user_agent})

        json_payload = json.dumps(payload)
        # ("sending {0} to {1} as {2}".format(payload, url, http_method.upper()))

        try:
            response = requests.request(http_method.upper(),
                                        url,
                                        headers=headers,
                                        data=json_payload,
                                        proxies=self.proxies,
                                        verify=self.https_verify)

            # store a copy of the request
            self._request = response.request

        # critical error: HTTP request resulted in an error!
        except Exception as err:
            # raise OTRSHTTPError("get http")
            raise HTTPError("Failed to access OTRS. Check Hostname, Proxy, SSL Certificate!\n"
                            "Error with http communication: {0}".format(err))

        if not response.status_code == 200:
            raise HTTPError("Received HTTP Error. Check Hostname and WebServiceName.\n"
                            "HTTP Status Code: {0.status_code}\n"
                            "HTTP Message: {0.content}".format(response))
        return response

    def _parse_and_validate_response(self, response):
        """_parse_and_validate_response

        Args:
            response (requests.Response): result of _send_request

        Raises:
            OTRSAPIError
            NotImplementedError
            ResponseJSONParseError

        Returns:
            **bool**: **True** if successful

        """

        if not isinstance(response, requests.models.Response):
            raise ValueError("requests.Response object expected!")

        if self.operation not in self.ws_config.keys():
            raise ValueError("invalid operation")

        # clear data from Client
        self.result = None
        self._result_error = False

        # get and set new data
        self.result_json = response.json()
        self._result_status_code = response.status_code
        self._result_content = response.content

        # handle TicketSearch operation first. special: empty search result has no "TicketID"
        if self.operation == "TicketSearch":
            if not self.result_json:
                self.result = []
                return True
            if self.result_json.get(self._result_type, None):
                self.result = self.result_json['TicketID']
                return True

        # handle Link operations; Add, Delete, DeleteAll return: {"Success":1}
        if self.operation in ["LinkAdd", "LinkDelete", "LinkDeleteAll"]:
            if self.result_json.get("Success", None) == 1:
                return True

        # LinkList result can be empty
        if self.operation in "LinkList":
            _link_list = self.result_json.get("LinkList", None)
            if not _link_list:
                self.result = None
                return True
            else:
                self.result = _link_list
                return True

        # PublicFAQSearch result can be empty
        if self.operation in "PublicFAQSearch":
            _public_faq_search_result_list = self.result_json.get(self._result_type, None)
            if not _public_faq_search_result_list:
                if self.result_json["Error"]["ErrorCode"] == "PublicFAQSearch.NotFAQData":
                    self.result = []
                    return True
            else:
                self.result = _public_faq_search_result_list
                return True

        # now handle other operations
        if self.result_json.get(self._result_type, None):
            self._result_error = False
            self.result = self.result_json[self._result_type]
        elif self.result_json.get("Error", None):
            self._result_error = True
        else:
            self._result_error = True
            # critical error: Unknown response from OTRS API - FAIL NOW!
            raise ResponseParseError("Unknown key in response JSON DICT!")

        # report error
        if self._result_error:
            raise APIError("Failed to access OTRS API. Check Username and Password! "
                           "Session ID expired?! Does Ticket exist?\n"
                           "OTRS Error Code: {0}\nOTRS Error Message: {1}"
                           "".format(self.result_json["Error"]["ErrorCode"],
                                     self.result_json["Error"]["ErrorMessage"]))

        # for operation TicketGet: parse result list into Ticket object list
        if self.operation == "TicketGet" or self.operation == "TicketGetList":
            self.result = [Ticket(item) for item in self.result_json['Ticket']]

        return True

# EOF
