"""Subject sex mapping based on file ID (first 2 digits)"""
SUBJECT_SEX_MAP = {
    '06': 'F', '08': 'F', '09': 'F', '10': 'F', '12': 'F', '14': 'F',
    '01': 'M', '02': 'M', '03': 'M', '05': 'M', '07': 'M', '11': 'M', '13': 'M',
}

def get_sex_from_filename(filename):
    """Extract subject ID (first 2 digits) and return sex."""
    try:
        subject_id = filename[:2]
        return SUBJECT_SEX_MAP.get(subject_id, None)
    except:
        return None