import warnings
import pandas as pd

from multiprocessing import Process
from mmeds.util import send_email
from mmeds.logging import Logger
from mmeds.database.database import Database


class AliquotUploader(Process):
    def __init__(self, owner, access_code, aliquot_table, testing):
        """
        Connect to the specified database.
        Initialize variables for this session.
        ====================================
        :owner: The user who is uploading these aliquots
        :aliquot_table: Filepath to the aliquots being uploaded
        """
        warnings.simplefilter('ignore')
        super().__init__()
        Logger.info(f'Creating an Aliquot ID Generator for user {owner}')
        self.owner = owner
        self.aliquot_table = aliquot_table
        self.testing = testing
        self.access_code = access_code

    def run(self):
        """ Perform the uploads """

        with Database(testing=self.testing, owner=self.owner) as db:
            mdata = db.get_doc(access_code=self.access_code)
            mdata.update(is_alive=True, exit_code=None)
            mdata.save()
            df = pd.read_csv(self.aliquot_table, sep='\t')
            for index, row in df.iterrows():
                db.generate_aliquot_id(row['StudyName'], row['SpecimenID'], row['AliquotWeight'])

            email = db.get_email(self.owner)
            # Update the doc to reflect the successful upload
            mdata.update(is_alive=False, exit_code=0)
            mdata.save()

        # Send the confirmation email
        send_email(email, self.owner,
                   message='ids_generated',
                   testing=self.testing,
                   id_type='aliquot',
                   study=df['StudyName'][0])

        return 0
