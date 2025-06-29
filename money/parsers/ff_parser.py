# money/parsers/ff_parser.py
from .generic_csv_parser import GenericCsvParser

class FFStatementParser(GenericCsvParser):
    """
    Parser for Freedom Finance statements.
    It currently reuses the logic from GenericCsvParser.
    """
    def __init__(self, file_content):
        # Call the parent's constructor to correctly initialize
        super().__init__(file_content)

    def parse(self):
        # Call the parent's (GenericCsvParser) parse method to do the actual work.
        parsed_data = super().parse()

        for transaction in parsed_data['transactions']:
            transaction['place'] = ''
            if transaction.get('to_account'):
                transaction['type'] = 'transfer'

        parsed_data['header']['currency'] = 'KZT'
        
        return parsed_data