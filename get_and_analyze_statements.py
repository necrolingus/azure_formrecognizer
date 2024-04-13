import requests
import json
import xmltodict
import sys
import time
import os
import csv

#There are some strict limits in the free tier. Read more here:
#https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0

#Prep Work
#Lets create the directory where we will dump all our json analysis results
#as well as our CSV files
#We will just put it in the location of where we are executing our script from
#Lets keep it compatible with older versions of python especially < 3.5
path_to_dump_analysis = "analysis_json"
path_to_csv_output = "csv_output"

isExist = os.path.exists(path_to_dump_analysis)
if not isExist:
    os.makedirs(path_to_dump_analysis)

isExist = os.path.exists(path_to_csv_output)
if not isExist:
    os.makedirs(path_to_csv_output)


#Step 0: Build up variables
#Build up generic variables
sleep_time_between_analyze = 2 #just sleep a bit because we are on the free tier
sleep_time_before_getting_analysis = 90 #can do this better, but for now this is fine
transaction_list = []
turnover_list = []
transaction_csv_output_file_name = "all_transactions.csv"
turnover_csv_output_file_name = "all_turnover.csv"

#Build up blob container variables so we can list our files
sas_url = "https://xxx.blob.core.windows.net/mystatementstocheck/"
sas_url_parameters = "restype=container&comp=list"
sas_url_token = "xxx"
list_of_file_names = []

#Build up formrecognizer variables so we can pass a file to our model
formrecognizer_base_url = "https://xxx.cognitiveservices.azure.com/formrecognizer/documentModels/"
formrecognizer_model_id = "xxx"
formrecognizer_api_version = "api-version=2023-07-31"
formrecognizer_secret_key = "xxx"
formrecognizer_headers = {"Ocp-Apim-Subscription-Key": formrecognizer_secret_key, "Content-Type":"application/json"}
formrecognizer_url = "{}{}:analyze?{}".format(formrecognizer_base_url, formrecognizer_model_id, formrecognizer_api_version)
list_of_operation_locations = [] #We will send our file for analysis, then this header will contain where to get the results


#Step 1: Get a list of files in your Azure Blob Storage container
print("Getting a list of all our files in our blob container")
r = requests.get("{}?{}&{}".format(sas_url, sas_url_parameters, sas_url_token))
response_code = r.status_code

if response_code == 200:
    files_dict_dump = json.dumps(xmltodict.parse(r.text), indent=4)
    list_of_files = json.loads(files_dict_dump)["EnumerationResults"]["Blobs"]["Blob"]
    list_of_file_names = [f_name["Name"] for f_name in list_of_files]
else:
    print("Oh no! Our container list response code was not 200, it was {}!".format(response_code))


#Step 2: Enumerate over those files you just got and send them to the formrecognizer service
#to analyze them and store the "Operation-Location" response in another list so we can fetch the results
#of the analysis
#"Operation-Location" is the endpoint we must call to get the results of this analysis step
print("Now sending those blobs to formrecognizer for analysis. We will sleep for {} seconds between requests".format(sleep_time_between_analyze))
if len(list_of_file_names) > 0:
    for file_name in list_of_file_names:
        file_location = "{}{}?{}".format(sas_url, file_name, sas_url_token)
        data_to_pass = {"urlSource":file_location}

        r = requests.post(formrecognizer_url, headers=formrecognizer_headers, data=json.dumps(data_to_pass))
        response_code = r.status_code

        if response_code == 202:
            operation_location_endpoint = r.headers.get('Operation-Location', None)
        
            if operation_location_endpoint is not None:
                list_of_operation_locations.append({"file_name":file_name, "operation_location_endpoint": operation_location_endpoint})
        else:
            print("Oh no! Our formrecognizer analyze response code was not 200, it was {}!".format(response_code))

        time.sleep(sleep_time_between_analyze)
else:
    print("Damn, we don't have any files. Our files list is empty!")


#Step 3: Now we should have data in our list_of_operation_locations list.
#So lets enumerate over these endpoints and get the results of our analysis into CSV format
#We will sleep a bit so we can wait for our analysis to be ready. This can probably be done better
#but for now sleep will do
print("We will now get the results of our analysis, but we will sleep for {} seconds first".format(sleep_time_before_getting_analysis))
if len(list_of_operation_locations) > 0:
    time.sleep(sleep_time_before_getting_analysis)
    for analysis_results in list_of_operation_locations:
        r = requests.get(analysis_results["operation_location_endpoint"], headers=formrecognizer_headers)
        response_code = r.status_code

        if response_code == 200:
            file_name_json = analysis_results["file_name"].split(".")[0]+".json"
            full_path = os.path.join(path_to_dump_analysis, file_name_json)
            with open(full_path, "w") as dump_json:
                dump_json.write(r.text)
        else:
            print("Oh no! Our fetching analysis response code was not 200, it was {}!".format(response_code))
else:
    print("Damn, we don't have any operation locations. Our analyze list is empty!")


#Step 4: Now lets read all those dumped json files and get the transactions into a list
#and then into a CSV file
print("And now we will take all our results and create nice CSV files")
dir_list = os.listdir(path_to_dump_analysis)
json_dump_files = [os.path.join(path_to_dump_analysis, file) for file in os.listdir(path_to_dump_analysis) if file.endswith('.json')]

for json_dump_file in json_dump_files:

    with open(json_dump_file, "r") as file1:
        file_contents = file1.read()
        json_contents = json.loads(file_contents)

    #Get the statement year
    statement_period = json_contents["analyzeResult"]["documents"][0]["fields"]["StatementPeriod"]["valueString"]
    statement_year = str(statement_period.strip()[-4:])

    #Get the list objects of our analyzed tables
    transactions = json_contents["analyzeResult"]["documents"][0]["fields"]["Transactions"]["valueArray"]
    turnovers = json_contents["analyzeResult"]["documents"][0]["fields"]["Turnover"]["valueArray"]

    for transaction in transactions:
        transaction_list.append({
            "trn_date": "{} {}".format(transaction["valueObject"]["Date"]["valueString"], statement_year),
            "trn_description": transaction["valueObject"]["TrnDescription"]["valueString"],
            "trn_amount": (transaction["valueObject"]["Amount"]["valueString"]).replace(",",""),
            "trn_balance": (transaction["valueObject"]["Balance"]["valueString"]).lower().replace("cr",'').replace(" ","").replace(",",""),
            "in_out": "in" if ((transaction["valueObject"]["Amount"]["valueString"]).lower())[-2:] == "cr" else "out" ,
            "line_confidence": "{:.2f}".format(float(transaction["confidence"])*100)
        })

    for turnover in turnovers:
        turnover_list.append({
            "statement_period": statement_period,
            "credit_debit": turnover["valueObject"]["CreditDebit"]["valueString"],
            "number_of_transactions": turnover["valueObject"]["NumberOfTransactions"]["valueString"],
            "turnover_amount": (turnover["valueObject"]["Amount"]["valueString"]).lower().replace("cr",'').replace(" ","").replace(",",""),
            "line_confidence": "{:.2f}".format(float(turnover["confidence"])*100)
        })

#Lets create the paths to output our CSV files
transaction_csv_output_full_path = os.path.join(path_to_csv_output, transaction_csv_output_file_name)
turnover_csv_output_full_path = os.path.join(path_to_csv_output, turnover_csv_output_file_name)

#Lets create the field names for our CSV file
transaction_field_names = [k for k, v in transaction_list[0].items()]
turnover_field_names = [k for k, v in turnover_list[0].items()]

#Now lets write the transaction file
with open(transaction_csv_output_full_path, mode='w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=transaction_field_names)
    writer.writeheader()
    writer.writerows(transaction_list)

#And now the turnover file
with open(turnover_csv_output_full_path, mode='w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=turnover_field_names)
    writer.writeheader()
    writer.writerows(turnover_list)
