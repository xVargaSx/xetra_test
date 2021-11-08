"""
Methods for processing the meta file
"""
import collections
from datetime import datetime, timedelta
from types import MethodWrapperType
import pandas as pd
from xetra.common.constants import MetaProcessFormat
import xetra.common.custom_exceptions
from xetra.common.s3 import S3BucketConnector


class MetaProcess():
    """
    Class for working with the meta file
    """

    @staticmethod
    def update_meta_file(extract_date_list: list, meta_key: str, s3_bucket_meta: S3BucketConnector):
        """
        Updating the meta file with the processed Xetra dates and
            todays date as processed extract_date_list

        :param: extract_date_list -> a list of dates that are extracted from the source
        :param: meta_key -> key of the meta file on the S3 bucket
        :param: s3_bucket_meta -> S3BucketConnector for the bucket with the meta file
        """
        # creating an empty DataFrame using the meta file column names
        df_new = pd.DataFrame(columns=[
            MetaProcessFormat.META_SOURCE_DATE_COL.value,
            MetaProcessFormat.META_PROCESS_COL.value])
        # filling the date column with extract_date_list
        df_new[MetaProcessFormat.META_SOURCE_DATE_COL.value] = extract_date_list
        # filling the processed column
        df_new[MetaProcessFormat.META_PROCESS_COL.value] = \
            datetime.today().strftime(MetaProcessFormat.META_PROCESS_DATE_FORMAT.value)
        try:
            # if meta file exists -> union DataFrame of old and new meta date is created
            df_old = s3_bucket_meta.read_csv_to_df(meta_key)
            if collections.Counter(df_old.columns) != collections.Counter(df_new.columns):
                raise xetra.common.custom_exceptions.WrongMetaFileException
            df_all = pd.concat([df_old, df_new])
        except s3_bucket_meta.session.client('s3').exceptions.NoSuchKey:
            # No meta file exists -> only the new data is used
            df_all = df_new
        # writing to S3
        s3_bucket_meta.write_df_to_s3(df_all, meta_key, MetaProcessFormat.META_FILE_FORMAT.value)
        return True

    @staticmethod
    def return_date_list(first_date: str, meta_key: str, s3_bucket_meta: S3BucketConnector):
        """
        Creating a list of dates based on the input first_date and the already
        processed dates in the meta file

        :param: first_date -> the earliest date Xetra data should be processed
        :param: meta_key -> key of the meta file on the S3 bucket
        :param: s3_bucket_meta -> S3BucketConnector for the bucket with the meta file

        returns:
            min_date: first date that should be processed
            return_date_list: list of all dates from min_date till today
        """

        start_dt = datetime.strptime(first_date, MetaProcessFormat.META_DATE_FORMAT.value).date()\
            - timedelta(days=1)
        today = datetime.today().date()
        try:
            # if meta file exists create return_date_list using the content of the meta file
            # reading meta file
            df_meta = s3_bucket_meta.read_csv_to_df(meta_key)
            # creating a list of dates from first_date until today
            dates = [(start_dt + timedelta(days=x)) for x in range(0, (today-start_dt).days )] #+ 1
            # creating a list of dates from min_date until today
            src_dates = set(pd.to_datetime(
                df_meta[MetaProcessFormat.META_SOURCE_DATE_COL.value]).dt.date)
            dates_missing = set(dates[1:]) - src_dates
            if dates_missing:
                # determining the earliest date that should be
                min_date = min(set(dates[1:]) - src_dates) - timedelta(days=1)
                # creating a list of dates from min_date until today
                return_min_date = (min_date + timedelta(days=1))\
                    .strftime(MetaProcessFormat.META_DATE_FORMAT.value)
                return_dates = [
                    date.strftime(MetaProcessFormat.META_DATE_FORMAT.value)\
                        for date in dates if date >= min_date
                ]
            else:
                # setting values for the earliest date and the list of dates
                return_dates = []
                return_min_date = datetime(2200, 1, 1).date()\
                    .strftime(MetaProcessFormat.META_DATE_FORMAT.value)
        except s3_bucket_meta.session.client('s3').exceptions.NoSuchKey:
            # no meta file found -> creating a date list from first_date - 1 day until today
            return_min_date = first_date
            return_dates = [
                (start_dt + timedelta(days=x)).strftime(MetaProcessFormat.META_DATE_FORMAT.value)\
                     for x in range(0, (today-start_dt).days + 1)]

        return return_min_date, return_dates
