from mmeds.util import simplified_to_full
import mmeds.validate as valid
from pathlib import Path
print('Checking Subject')
errors, warnings, subjects = valid.validate_mapping_file('/home/david/Work/minerva/data/Lee_Tran/GRAPHS_Subject.tsv',
                                                         'GRAPHS',
                                                         'subject',
                                                         None,
                                                         'human')

print('Checking Specimen')
errors, warnings, subjects = valid.validate_mapping_file('/home/david/Work/minerva/data/Lee_Tran/GRAPHS_Specimen.tsv',
                                                         'GRAPHS',
                                                         'specimen',
                                                         subjects,
                                                         'human')
for error in errors:
    print(error)
