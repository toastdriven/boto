#!/usr/bin/env python
# Copyright (c) 2012 Amazon.com, Inc. or its affiliates.  All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from tests.unit import unittest
from tests.unit import AWSMockServiceTestCase

from boto.exception import BotoServerError
from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket


class TestS3Key(AWSMockServiceTestCase):
    connection_class = S3Connection

    def setUp(self):
        super(TestS3Key, self).setUp()

    def default_body(self):
        return "default body"

    def test_when_no_restore_header_present(self):
        self.set_http_response(status_code=200)
        b = Bucket(self.service_connection, 'mybucket')
        k = b.get_key('myglacierkey')
        self.assertIsNone(k.ongoing_restore)
        self.assertIsNone(k.expiry_date)

    def test_restore_header_with_ongoing_restore(self):
        self.set_http_response(
            status_code=200,
            header=[('x-amz-restore', 'ongoing-request="true"')])
        b = Bucket(self.service_connection, 'mybucket')
        k = b.get_key('myglacierkey')
        self.assertTrue(k.ongoing_restore)
        self.assertIsNone(k.expiry_date)

    def test_restore_completed(self):
        self.set_http_response(
            status_code=200,
            header=[('x-amz-restore',
                     'ongoing-request="false", '
                     'expiry-date="Fri, 21 Dec 2012 00:00:00 GMT"')])
        b = Bucket(self.service_connection, 'mybucket')
        k = b.get_key('myglacierkey')
        self.assertFalse(k.ongoing_restore)
        self.assertEqual(k.expiry_date, 'Fri, 21 Dec 2012 00:00:00 GMT')

    def test_delete_key_return_key(self):
        self.set_http_response(status_code=204, body='')
        b = Bucket(self.service_connection, 'mybucket')
        key = b.delete_key('fookey')
        self.assertIsNotNone(key)


def counter(fn):
    def _wrapper(*args, **kwargs):
        _wrapper.count += 1
        return fn(*args, **kwargs)
    _wrapper.count = 0
    return _wrapper


class TestS3KeyRetries(AWSMockServiceTestCase):
    connection_class = S3Connection

    def setUp(self):
        super(TestS3KeyRetries, self).setUp()

    def test_500_retry(self):
        self.set_http_response(status_code=500)
        b = Bucket(self.service_connection, 'mybucket')
        k = b.new_key('test_failure')
        fail_file = StringIO('This will attempt to retry.')

        try:
            k.send_file(fail_file)
            self.fail("This shouldn't ever succeed.")
        except BotoServerError:
            pass

    def test_400_timeout(self):
        weird_timeout_body = "<Error><Code>RequestTimeout</Code></Error>"
        self.set_http_response(status_code=400, body=weird_timeout_body)
        b = Bucket(self.service_connection, 'mybucket')
        k = b.new_key('test_failure')
        fail_file = StringIO('This will pretend to be chunk-able.')

        # Decorate.
        k.chunked_retry_handler = counter(k.chunked_retry_handler)
        self.assertEqual(k.chunked_retry_handler.count, 0)

        try:
            k.send_file(fail_file)
        except BotoServerError:
            pass

        self.assertTrue(k.chunked_retry_handler.count > 5)


if __name__ == '__main__':
    unittest.main()
