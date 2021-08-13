from mmeds.util import simplified_to_full
import mmeds.validate as valid
from pathlib import Path
errors, warnings, subjects = valid.validate_mapping_file('/home/david/Work/minerva/data/Lee_Tran/GRAPHS_Subject.tsv',
                                                         'GRAPHS',
                                                         'subject',
                                                         None,
                                                         'human')

new_path = Path('/home/david/Work/minerva/data/Lee_Tran/GRAPHS_Specimen.tsv')
simplified_to_full('/home/david/Work/minerva/data/Lee_Tran/Lee_Specimen_clean.tsv', new_path, 'specimen')
errors, warnings, subjects = valid.validate_mapping_file(new_path,
                                                         'GRAPHS',
                                                         'specimen',
                                                         subjects,
                                                         'human')
for error in errors:
    print(error)
