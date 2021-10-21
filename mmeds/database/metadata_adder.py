import warnings
import pandas as pd

from multiprocessing import Process
from mmeds.error import InvalidUploadError
from mmeds.util import send_email
from mmeds.logging import Logger
from mmeds.database.database import Database


class MetaDataAdder(Process):
    """
    The class used for uploading additional metadata to an existing study
    """
    def __init__(self, owner, access_code, id_table, id_type, generate_ids, testing):
        """
        Connect to the specified database.
        Initialize variables for this session.
        ====================================
        :owner: The user who is uploading these aliquots
        :access_code: Access code for the study this data is associated with
        :id_table: Filepath to the ids being uploaded
        :generate_ids: A boolean. If true generate new IDs. If False, they're included.
        """
        warnings.simplefilter('ignore')
        super().__init__()
        Logger.info(f'Creating an Aliquot ID Generator for user {owner}')
        self.owner = owner
        self.id_table = id_table
        self.testing = testing
        self.access_code = access_code
        self.id_type = id_type
        self.generate_ids = generate_ids

    def run(self):
        """ Perform the uploads """

        df = pd.read_csv(self.id_table, sep='\t')
        with Database(testing=self.testing, owner=self.owner) as db:
            mdata = db.get_doc(access_code=self.access_code)
            mdata.update(is_alive=True, exit_code=None)
            mdata.save()

            # Keep logic outside the loop
            # Move to a switch statement in the loop when moving to 3.10
            if self.id_type == 'aliquot':
                generate_method = db.generate_aliquot_id
            elif self.id_type == 'sample':
                generate_method = db.generate_sample_id
            elif self.id_type == 'subject':
                generate_method = db.add_subject_data
            else:
                raise InvalidUploadError(f'{self.id_type} is not a valid upload type')

            # Insert the values for every row
            for index, row in df.iterrows():
                generate_method(generate_id=self.generate_ids, **row.to_dict())

            email = db.get_email(self.owner)
            # Update the doc to reflect the successful upload
            mdata.update(is_alive=False, exit_code=0)
            mdata.save()

        # Send the confirmation email
        send_email(email, self.owner,
                   message='ids_generated',
                   testing=self.testing,
                   id_type=self.id_type,
                   study=df['StudyName'][0])

        # Return 0 if all completes successfully
        return 0
