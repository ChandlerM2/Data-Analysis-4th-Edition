# Learned & Understood

## Using UV

`uv python pin 3.14` pushes the .python-version file to be python version 3.14. note that in the pyproject.toml file we have `requires-python = ">=3.12"` which does a similar job.

`uv sync` when you first open on a new machine as it will install all the dependencies and create your .venv

## Data Analysis Process Methodologies

### Knowledge Discovery from Data (KDD)

If you are asked a question about the data how do you find the relationships?

- the process of finding patterns, insights, and relationships from large quantiteis of data to support knowledge discovery and decision making. **We are mostly looking for hidden patterns in the data here**

This process helps to gather, identify the problems, query, transform, analyze (mine), evaluate, and present information in a ***loop***. Note that this is not a strict order of operations. generally steps 1-4 can happen as a non-linear cycle called **preprocessing**.

1. **Data Cleaning**: handle noisy data, missing values, duplicates, and outliers in the given data we are pulling from
2. **Data Integration**: use a data migration tech to gather the data from sevreral sources and combine it into one system
3. **Data selection**: pull out relevant data recirds and columns (filters) based on the problem statement for the purpose of data analysis
4. **Data Transformation**: convert the raw data to a suitable format for data analysis depending on the input being a machine or person
5. **Data Mining**: we are discovering hidden patterns or associations in teh data via data mining techniques. These include, but are not exaused by: regressions, classification, clustering, anomaly detection, assocaitiaon rule mining, and recommender systems.
6. **Pattern Evaluation**:   the patterns found are measured and assessed in order to test the performance of data mining tehcniques (measure the results). It may also ask if the pattern is useful at all and can be acted on. 
7. **Knowledge Presentation**: After pattern evaluation, the discovered knowledge is presented to the decision making team via graphs and visuals.

The ***loop*** meantioned above is actually a feedback loop. The person doing the analysis drives the loop and it's generally not in step order (one at a time in order). generally when an analyst reaches a later step and learns something they will go back to an earlier step with that knowledge to work on it. The Knowledge discovery from data process stops when the discovery is worthy enough for an answer to the problem statement. 

**EXAMPLE:**  You mine vendor lead times and find a cluster of vendors with lead times near zero. At
  pattern evaluation (step 6) you dig in and find those are drop-ship orders with no real receipt date. That's a data problem, so you go back to cleaning and handle drop ships separately. You run it again, present it to the buyers, and they ask, "What does this look like by warehouse?" Now you're back at selection, pulling a column you left out.
  
  As noticed above each pass changes an earlier step because you know more than you did last time.


### Sample, Explore, Modfiy, Model, and Assess (SEMMA)
- this is mostly used in the SAS Enterpise Miner software and helps to build the prediciton model.

### CRoss-InduStry Process for Data Mining (CRISP-DM)

**First, What a sexy name**

This model is a well defined and orginized way to develop Data Mining, Machine Learning, and Business intellegence initiatives. It's well suited to solving business problems at larger corporations becuase of the steps below:

1. **Business Understanding** : we need to udnerstand the clients requirements and identify the problem statement. We can then design the analytic solution for the problem and develop an initial execution plan.

2. **Data Understanding** : We have to udnerstand the dataset here. That means udnerstanding the meaning of colums, how a story reads across rows, integreation process, data quality checks, exploration of the data, and some small insights that can be verified.

3. **Data Preparation** : Now we need to prepare the data to be analytics-ready. this means dealing with missing values, anomoly detection, transforamtions, feature scaling (we will talk about this later), and feature engineering to name a few. ***This will consume most of your time as an analyst or data scientist.***  

4. **Modeling** : the machine learning or data mining model is developed for wahtever the business case may be such as forcasting events, highlighting when data is put in wrong, ect. In this case the time will be mostly spent on deciding what type of model soles the business problem described in the **Business Understanding Stage**. 

5. **Evaluation** : the model is built we must test it against evaluation and assessment metrics such as mean square error (MSE), Mean Absolute Error (MAPE), Root Mean Square Error (RSME), and others depending on the model.

6. **Deployment** : is the trained model is deployed into production we will need to collaborate with the data sceince, frontend, backend, DevOps engineering, and business analysis teams. 

Note that most of the emphasis in CRISP-DM is in the model deployment and business context gathering stages.

<br>
<p align="center">
  <img src="../Pictures/CRISP-DM%20Chapter%201.png" alt="CRISP-DM Cycle">
</p>

### Personal Comments On These Frameworks 

Due to the circular nature of these evaluation loops we need some form of measurement to know if we are getting closer or further from out goal. This is important because in theory if we know the data well enough and how to guide an agent we could have an agent, work and test models and ideas to eventually deploy to the world. 

Something more fundamental is you generally dont know until you find the mistakes and learn from the information. Learning is not about knowing, it seems to be about finding the unknown and working with it to make your model better... there is probably a life lesson in that!


## GitHub

 - in github you can press the `.` to open a vitual codespace that is similar to VSCODE.
 - `git restore {item here}` will restore the file to its previous commited state
 this  

## .gitignore

- plain names like `.venv` match a file or folder with that name across all depths =
- in something like `__pycache__/` it will only match to the pychase folder, but specifically at any depth
- `*` matches any run of characters, so `*.pyc` matches any file ending in pyc
-  `/data/` only ignores a hypothetical data folder if in the same root (level of the directory) based on where the .gitignore file lives

## Pyspark

**Pyspark:**  is Apache Spark, a program written in Scalas, API wrapper. It s distributed computing engine that does the paraellel processing work. It is incredibly quick when comapred to MapReduce because it writes into memory instead of disk. 

you will need to install Java because it uses JRE (rava runtime environments) under the hood.

### Other tools in the Spark Ecosystem

**Spart SQL:** dataframes that you can query using SQL, but distributed. This is what the pySpark dataframe API mostly is according to claude.
**Spark Streaming / Structured Streaming:** processes live/real-time data feeds
**MLlib** distributed complute to ML alogs
**GraphX** Graphs processing.

## Databricks

**Databricks:** the cloud based apachie spark, that provides data visualizations, automations, scheduled tasks, and managed services. It is free via a community edition to learn and practice.

you can create an account via [Databricks Free Page](https://docs.databricks.com/aws/en/getting-started/free-edition)

