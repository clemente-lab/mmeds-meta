#! /usr/bin python3
from mmeds.spawn import handle_data_upload
from sys import argv
from pathlib import Path

# testing = False
testing = True
username = 'tankou'
reads_type = 'paired_end_demuxed'
metadata = Path(argv[1])
data = Path(argv[2])

datafile = open(data, 'rb')
import_data = [('for_reads', data, datafile)]  # , ('rev_reads', None, None), ('barcodes', None, None)]
handle_data_upload(metadata, username, reads_type, testing, *import_data)
