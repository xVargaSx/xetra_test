""" Tests the MetaProcess class methods"""

from io import StringIO
import os
import unittest
from datetime import datetime, timedelta

import boto3
from moto import mock_s3
import pandas as pd

from xetra.common.custom_exceptions import WrongMetaFileException
from xetra.common.constants import MetaProcessFormat
from xetra.common.meta_process import MetaProcess
from xetra.common.s3 import S3BucketConnector

class TestMetaProcessClassMethods(unittest.TestCase):
    """
    Testing the MetaProcess class
    """

    def setUp(self):
        """
        Setting up the environment
        """
        # mocking s3 connection start
        self.mock_s3 = mock_s3()
        self.mock_s3.start()
        # defining the class arguments
        self.s3_access_key = 'AWS_ACCESS_KEY_ID'
        self.s3_secret_key = 'AWS_SECRET_ACCESS_KEY'
        self.s3_endpoint_url = 'https://s3.eu-central-1.amazonaws.com'
        self.s3_bucket_name = 'test-bucket'
        # creating s3 access keys as environment variables
        os.environ[self.s3_access_key] = 'KEY1'
        os.environ[self.s3_secret_key] = 'KEY2'
        # creating bucket on the mocked s3
        self.s3 = boto3.resource(service_name='s3', endpoint_url=self.s3_endpoint_url)
        self.s3.create_bucket(Bucket=self.s3_bucket_name,
                              CreateBucketConfiguration={
                                  'LocationConstraint': 'eu-central-1'
                              })
        self.s3_bucket = self.s3.Bucket(self.s3_bucket_name)
        # creating a testing instance
        self.s3_bucket_meta = S3BucketConnector(self.s3_access_key,
                                                self.s3_secret_key,
                                                self.s3_endpoint_url,
                                                self.s3_bucket_name)
        self.dates = [(datetime.today().date() - timedelta(days=day)) \
            .strftime(MetaProcessFormat.META_DATE_FORMAT.value) for day in range(8)]

    def tearDown(self):
        """
        Executing after unittests
        """
        # mocking s3 connection stop
        self.mock_s3.stop()

    def test_update_meta_file_no_meta_file(self):
        """
        Tests the update_meta_file method
        when there is no meta file
        """
        # expected results
        date_list_exp = ['2021-04-16', '2021-04-17']
        proc_date_list_exp = [datetime.today().date()] * 2
        # test init
        meta_key = 'meta.csv'
        # method execution
        MetaProcess.update_meta_file(date_list_exp, meta_key, self.s3_bucket_meta)
        # read meta file
        data = self.s3_bucket.Object(key=meta_key).get().get('Body').read().decode('utf-8')
        out_buffer = StringIO(data)
        df_meta_result = pd.read_csv(out_buffer)
        date_list_result = list(df_meta_result[MetaProcessFormat.META_SOURCE_DATE_COL.value])
        proc_date_list_result = list(
            pd.to_datetime(df_meta_result[MetaProcessFormat.META_PROCESS_COL.value]).dt.date)
        # test after method execution
        self.assertEqual(date_list_exp, date_list_result)
        self.assertEqual(proc_date_list_exp, proc_date_list_result)
        #cleanup after test
        self.s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': meta_key
                    }
                ]
            }
        )

    def test_update_meta_file_empty_date_list(self):
        """
        Tests the update_meta_file method
        when the argument extract_date_list is empty
        """
        # expected results
        return_exp = True
        log_exp = 'The dataframe is empty! No file will be written!'
        # test init
        date_list = []
        meta_key = 'meta.csv'
        # method execution
        with self.assertLogs() as logm:
            result = MetaProcess.update_meta_file(date_list, meta_key, self.s3_bucket_meta)
            # log test after method execution
            self.assertIn(log_exp, logm.output[1])
        # test after method execution
        self.assertEqual(return_exp, result)

    def test_update_meta_file_meta_file_ok(self):
        """
        Tests the update_meta_file method
        when there already a meta file
        """
        # expected results
        date_list_old = ['2021-04-12', '2021-04-13']
        date_list_new = ['2021-04-16', '2021-04-17']
        date_list_exp = date_list_old + date_list_new
        proc_date_list_exp = [datetime.today().date()] * 4
        # test init
        meta_key = 'meta.csv'
        meta_content = (
            f'{MetaProcessFormat.META_SOURCE_DATE_COL.value},'
            f'{MetaProcessFormat.META_PROCESS_COL.value}\n'
            f'{date_list_old[0]},'
            f'{datetime.today().strftime(MetaProcessFormat.META_PROCESS_DATE_FORMAT.value)}\n'
            f'{date_list_old[1]},'
            f'{datetime.today().strftime(MetaProcessFormat.META_PROCESS_DATE_FORMAT.value)}'
        )
        self.s3_bucket.put_object(Body=meta_content, Key=meta_key)
        # method execution
        MetaProcess.update_meta_file(date_list_new, meta_key, self.s3_bucket_meta)
        # read meta file
        data = self.s3_bucket.Object(key=meta_key).get().get('Body').read().decode('utf-8')
        out_buffer = StringIO(data)
        df_meta_results = pd.read_csv(out_buffer)
        date_list_result = list(df_meta_results[MetaProcessFormat.META_SOURCE_DATE_COL.value])
        proc_date_list_result = list(pd.to_datetime(df_meta_results[
            MetaProcessFormat.META_PROCESS_COL.value]).dt.date)
        # test after execution
        self.assertEqual(date_list_exp, date_list_result)
        self.assertEqual(proc_date_list_exp, proc_date_list_result)
        #cleanup after test
        self.s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': meta_key
                    }
                ]
            }
        )

    def test_update_meta_file_meta_file_wrong(self):
        """
        Tests the update meta file method
        when there is a wrong meta file
        """
        # expected results
        date_list_old = ['2021-04-12', '2021-04-13']
        date_list_new = ['2021-04-16', '2021-04-17']
        # test init
        meta_key = 'meta.csv'
        meta_content = (
            f'wrong_column,'
            f'{MetaProcessFormat.META_PROCESS_COL.value}\n'
            f'{date_list_old[0]},'
            f'{datetime.today().strftime(MetaProcessFormat.META_PROCESS_DATE_FORMAT.value)}\n'
            f'{date_list_old[1]},'
            f'{datetime.today().strftime(MetaProcessFormat.META_PROCESS_DATE_FORMAT.value)}'
        )
        self.s3_bucket.put_object(Body=meta_content, Key=meta_key)
        # method execution
        with self.assertRaises(WrongMetaFileException):
            MetaProcess.update_meta_file(date_list_new, meta_key, self.s3_bucket_meta)
        #cleanup after test
        self.s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': meta_key
                    }
                ]
            }
        )

    def test_return_date_list_no_meta_file(self):
        """
        Tests the return_date_list method
        when there is no meta file
        """
        # expected results
        date_list_exp = [
            (datetime.today().date() - timedelta(days=day))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value) for day in range(4)
        ]
        min_date_exp = (datetime.today().date() - timedelta(days=2))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value) 
        # test init
        first_date = min_date_exp
        meta_key = 'meta.csv'
        # method execution
        min_date_return, date_list_return = MetaProcess.return_date_list(first_date, meta_key, 
                                                                         self.s3_bucket_meta)
        # test after method execution
        self.assertEqual(set(date_list_exp), set(date_list_return))
        self.assertEqual(min_date_exp, min_date_return)

    def test_return_date_list_meta_file_ok(self):
        """
        Testst the return_date_list method
        when there is a meta file
        """
        # expected results
        min_date_exp = [
            (datetime.today().date() - timedelta(days=1))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value),
            (datetime.today().date() - timedelta(days=2))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value),
            (datetime.today().date() - timedelta(days=7))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value)
        ]
        date_list_exp = [
            [(datetime.today().date() - timedelta(days=day))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value) for day in range(3)],
            [(datetime.today().date() - timedelta(days=day))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value) for day in range(4)],
            [(datetime.today().date() - timedelta(days=day))\
                .strftime(MetaProcessFormat.META_DATE_FORMAT.value) for day in range(9)]
        ]
        # test init
        meta_key = 'meta.csv'
        meta_content = (
            f'{MetaProcessFormat.META_SOURCE_DATE_COL.value},'
            f'{MetaProcessFormat.META_PROCESS_COL.value}\n'
            f'{self.dates[3]},{self.dates[0]}\n'
            f'{self.dates[4]},{self.dates[0]}\n'
        )
        self.s3_bucket.put_object(Body=meta_content, Key=meta_key)
        first_date_list = [
            self.dates[1],
            self.dates[4],
            self.dates[7]
        ]
        # method execution
        for count, first_date in enumerate(first_date_list):
            min_date_return, date_list_return = MetaProcess.return_date_list(first_date, meta_key,
                                                                             self.s3_bucket_meta)
            # test after method execution
            self.assertEqual(set(date_list_exp[count]), set(date_list_return))
            self.assertEqual(min_date_exp[count], min_date_return)
        # cleanup after test
        self.s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': meta_key
                    }
                ]
            }
        )

    def test_return_date_list_meta_file_wrong(self):
        """
        Tests the return_date_list method
        when there is a wrong meta file
        """
        # test init
        meta_key = 'meta.csv'
        meta_content = (
            f'wrong_column,'
            f'{MetaProcessFormat.META_PROCESS_COL.value}\n'
            f'{self.dates[3]},{self.dates[0]}\n'
            f'{self.dates[4]},{self.dates[0]}\n'
        )
        self.s3_bucket.put_object(Body=meta_content, Key=meta_key)
        first_date = self.dates[1]
        # method execution
        with self.assertRaises(KeyError):
            MetaProcess.return_date_list(first_date, meta_key, self.s3_bucket_meta)
        # cleanup after test
        self.s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': meta_key
                    }
                ]
            }
        )

    def test_return_date_list_empty_date_list(self):
        """
        Tests the return_date_list method
        when there are no dates to be returned
        """
        # expected results
        min_date_exp = '2200-01-01'
        date_list_exp = []
        # test init
        meta_key = 'meta.csv'
        meta_content = (
            f'{MetaProcessFormat.META_SOURCE_DATE_COL.value},'
            f'{MetaProcessFormat.META_PROCESS_COL.value}\n'
            f'{self.dates[0]},{self.dates[0]}\n'
            f'{self.dates[1]},{self.dates[0]}\n'
        )
        self.s3_bucket.put_object(Body=meta_content, Key=meta_key)
        first_date = self.dates[0]
        # method execution
        min_date_return, date_list_return = MetaProcess.return_date_list(first_date, meta_key,
                                                                         self.s3_bucket_meta)
        # test after method execution
        self.assertEqual(date_list_exp, date_list_return)
        self.assertEqual(min_date_exp, min_date_return)
        # cleanup after test
        self.s3_bucket.delete_objects(
            Delete={
                'Objects': [
                    {
                        'Key': meta_key
                    }
                ]
            }
        )

if __name__ == "__main__":
    unittest.main()