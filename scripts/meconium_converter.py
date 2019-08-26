import pandas as pd

mapping = {
    'brian.Type': ('Specimen', 'SpecimenType'),
    'gender.factor': ('Subjects', 'Sex'),
    'curr_height': ('Heights', 'Height'),
    'curr_weighr': ('Weights', 'Weight'),
    'race.factor': ('Ethnicity', 'Ethnicity')

}

# Ratio of original value to new value
conversions = {
    'curr_height': 0.0254,
    'curr_weight': 0.4536
}
