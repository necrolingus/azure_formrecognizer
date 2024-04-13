# Azure Form Recognizer for FNB (First National Bank) Statements
Everywhere where there is "xxx" in the code put the actual details


### Why did I do this?
- Because I wanted an easy way to get all transactions and turnovers from several months of FNB bank statements.
- FNB does not provide an easy way to just dump a list of transactions into CSV file. (At least there is no method that I know of).

### Do you want this model?

Azure does make it super easy to create models like this, but if you don't feel like labelling the tables and stuff yourself, reach out then I can do a model transfer or something.

The model accuracy is pretty good, 95% plus on almost everything which is good enough, but you can always add additional data for training.

### What can the model recognize?
- The statement period e.g. "29 March 2024 to 30 April 2024".
- The entire transaction table.
- The turnover table.

### What does this code do?

First you need to upload your FNB statements to a Azure Storage container, and then you create an Access Policy with Read and List permissions and get the SAS token and URL.

Then you give put this SAS URL into this code.

Then you let it do its thing. It will output 2 CSV files: 1 with all the transactions, 1 with all the turnover details.

And then, profit.
