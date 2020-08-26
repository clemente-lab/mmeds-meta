import pandas as pd


race_key = {
    1: 'Caucasian',
    2: 'Black',
    3: 'Asian',
    4: 'Hispanic',
    5: 'Other',
    6: 'Unknown'
}

def convert_age(age):
    return 2020 - age


def main():
    df = pd.read_excel('/home/david/Work/data_sets/segal/Mapping_file_SARS_0709_AS.1.NO_identifiers.After.Match.a9.xlsx')
    print(df)



if __name__ == '__main__':
    main()
