#! /usr/bin python3
from mmeds.spawn import handle_data_upload
from sys import argv
from pathlib import Path

testing = False
username = 'tankou'
reads_type = 'paired_end_demuxed'
metadata = Path(argv[1])
data = Path(argv[2])

with open(data) as f:
    import_data = [('for_reads', data, f), ('rev_reads', None, None), ('barcodes', None, None)]
    handle_data_upload(metadata, username, reads_type, testing, import_data)
