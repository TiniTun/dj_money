import csv
import re


def normalize_csv(input_file, output_file):
    #input_file = 'halyk.csv'
    #output_file = 'output.csv'

    with open(input_file, 'r', newline='', encoding='utf-8') as f_in, open(output_file, 'w', newline='', encoding='utf-8') as f_out:
        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        #prev_row = ['date_of_transaction', 'date_of_transaction_processing', 'transaction_description' ,'transaction_amount', 'transaction_currency', 'credit_in_account_currency', 'debit_in_account_currency', 'fee', 'card_number_account_number', 'account_currency']
        prev_row = []
        for row in reader:
            if re.match(r'^\d|^\s*,', ','.join(row)):
                # Если начинается с пустого значения, добавляем содержание текущей строки к предыдущей строке
                if re.match(r'^\s*,', ','.join(row)):
                    if prev_row:
                        prev_row[2] += ' ' + row[1].strip()
                        prev_row.append(row[-1].strip()[1:-1])
                else:
                    if prev_row:
                        writer.writerow(prev_row)
                    prev_row = row

        if prev_row:
            writer.writerow(prev_row)

    #print(f'Processed CSV file has been saved to {output_file}')
