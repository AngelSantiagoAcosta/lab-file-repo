""" QC for Lab data
# Author: Angel Acosta <angel.acosta@babsondx.com>
# Created 06/15/2022
"""

import os
import shutil
from types import NoneType
import pandas as pd 
import numpy as np
import datetime 
from datetime import datetime
from prefect import flow,task

def is_float(a_string):
    try:
        float(a_string)
        return True
    except ValueError:
        return False

def str_is_number(string):
    try:
        float(string)
        return True
    except ValueError:
        return False

def is_number(pd_series):
    type_series = []
    for i in pd_series.to_list():
        string_to_check = str(i).replace(" ", "")
        is_number = str_is_number(string_to_check)
        type_series.append(is_number)
    return pd.Series(type_series)


def test_result_convert_to_float(test_result_series):
    converted_series = []
    test_results = test_result_series.to_list()
    for result in test_results:
        new_result = str(result).strip(">").strip("<")
        if new_result.isnumeric():
            converted_series.append(float(new_result))
        elif is_float(new_result):
            converted_series.append(float(new_result))
        else:
            converted_series.append(np.nan)
    return pd.Series(converted_series)

@task
def validation_6(df):  #takes df, returns validation 6 series
    df["Validation 6"] = "" 
    condition1 = (df["Analyte"].astype(str) == "PLT-I") & (df["TestResultFlags"].isin(["W","A"]))
    sampleID_list = df.loc[condition1]["SampleID"].unique()
    for sampleID in sampleID_list:
        sample_filter = (df["SampleID"] == sampleID)
        record_ID = df.loc[sample_filter & condition1]["TestResultID"].to_list()[0]
        condition2 = np.any(np.where((df.loc[sample_filter]["Analyte"] == "PLTCLUMP") & (df.loc[sample_filter]["TestResultValue"].isnull()==False), True,False))
        condition3 = np.any(np.where((df.loc[sample_filter]["Analyte"] == "PLT_Clumps?") & (df.loc[sample_filter]["TestResultValue"].isnull()==False), True,False))
        condition4 = np.any(np.where((df.loc[sample_filter]["Analyte"] == "PLT_Clumps? Confirmed?") & (df.loc[sample_filter]["TestResultValue"].isnull()==False), True,False))
        df.loc[sample_filter  & (df["TestResultID"] == record_ID),"Validation 6"]= np.where((condition2)&(condition3)&(condition4) ,"passed","Flag on a PLT-I result and missing corresponding Records")
    return df["Validation 6"]


@task
def validation_7(df): #takes df, returns validation 7 series
    df["Validation 7"] = "" 
    condition1 =  (df["Origin"].astype(str) == "Sysmex XN-1000") & (df["TestResultFlags"].astype(str) =="A") # we might be too strict when looking at origin across the board.
    sampleID_list = df.loc[condition1]["SampleID"].unique() # this establishes which sampleIDs meet condition 1
    for sampleID in sampleID_list:
        sample_filter = (df["SampleID"] == sampleID)
        subset_df = df.loc[sample_filter]
        result_ID_list = subset_df.loc[condition1]["TestResultID"].to_list()
        analyte_to_check_list = df.loc[(sample_filter) &(condition1)]["Analyte"].astype(str).to_list() # should return a single result, NOT ALWAYS TRUE
        analyte_to_check_list = [ i+"?" if (("?" not in i) and (i!="PLT_Abn_Distribution")) else i  for i in analyte_to_check_list ]
        # analyte_to_check_list = [ i.replace("_"," ") if "_Lympho" in i else i for i in analyte_to_check_list ]
        record_dict = dict(zip(result_ID_list,analyte_to_check_list))
        for record_ID, analyte in record_dict.items():
            # Heath Said remove cond 2
            # condition2 = np.any(np.where((df.loc[sample_filter]["Analyte"].str.contains(analyte,na=False)) & (df.loc[sample_filter]["TestResultValue"].isnull()==False)))
            analyte_confirmed = analyte + " Confirmed?" 
            condition3 = np.any(np.where((subset_df["Analyte"].str.replace("_"," ") == analyte_confirmed.replace("_"," ")) & (subset_df["TestResultValue"].astype(str).isin(["Yes","No"])), True,False))
            df.loc[sample_filter & (df["TestResultID"] == record_ID),"Validation 7"]= np.where((condition3) ,"passed","Hematology result is not flagged as confirmed")
    return df["Validation 7"]

@task  
def validation_9(df):
    df["Validation 9"] = ""
    condition1 = (df["Repeat"] == "Y") & (df["Origin"].isin(val_9_origin_values))
    sampleID_list = df.loc[condition1]["SampleID"].unique()
    for sampleID in sampleID_list:
        sample_filter = (df["SampleID"] == sampleID)
        condition2 = (df["Repeat"] != "Y")
        resultID_list = df.loc[sample_filter & condition1]["TestResultID"].to_list()
        aspiration_origin_list = df.loc[sample_filter & condition1][["AspirationTimestamp","Origin"]].values.tolist()
        record_dict = dict(zip(resultID_list,aspiration_origin_list))
        for resultID, timestamp_origin in record_dict.items():
            test_comment_bool = df.loc[df["TestResultID"] == resultID]["Test Comments"].isnull().to_list()[0]
            cond_3_df = df.loc[condition2 & (df["Origin"] == timestamp_origin[1]) & sample_filter]
            condition3 = np.any(np.where((timestamp_origin[0] < cond_3_df["AspirationTimestamp"]),True, np.where((timestamp_origin[0] == cond_3_df["AspirationTimestamp"]) & (test_comment_bool),True,False)))
            df.loc[sample_filter & (df["AspirationTimestamp"] == timestamp_origin[0]) & (df["TestResultID"] == resultID),"Validation 9"]= np.where((condition3) ,"Aspiration Time of repeat test is not after initial tests","passed")        
    return df["Validation 9"]

@task
def validation_16(df):
    df["Validation 16"] = ""
    for analyte, decimal_place in val_16_analyte_dict.items():
        analtye_filter = ((df["Analyte"] == analyte)|(df["Method"] == analyte)) & (is_number(df["TestResultValue"].astype(str)))
        filtered_df = df.loc[analtye_filter]
        if decimal_place != 0:
            df.loc[analtye_filter,"Validation 16"] = np.where(filtered_df["TestResultValue"].astype(str).str[::-1].str.find('.')==decimal_place,"passed","Test Result does not contain correct decimal places")
        else:
            df.loc[analtye_filter,"Validation 16"] = np.where(filtered_df["TestResultValue"].astype(str).str[::-1].str.find('.') == -1,"passed","Test Result does not contain correct decimal places")
    return df["Validation 16"]


def found_tests_dict(df,sampleID_list):
    sampleID_tests_dict = {}
    for sampleID in sampleID_list: #array of unique IDs
        group_filter = (df["SampleID"]== sampleID) 
        found_tests = df.loc[group_filter]["Analyte"].to_list()
        sampleID_tests_dict.update({sampleID: found_tests})
    return sampleID_tests_dict

@task
def validation_20(df):
    df["Validation 20"] = ""
    unique_sampleIDs = df["SampleID"].unique()
    for sampleID in unique_sampleIDs:
        sample_filter = (df["SampleID"] == sampleID)
        duplicate_filter = (df.loc[sample_filter]["Analyte"].duplicated(keep=False) == True) & (df.loc[sample_filter]["Method"].duplicated(keep=False) == True)
        df.loc[sample_filter ,"Validation 20"] =np.where(duplicate_filter,"Test occured more than once per Sample ID","passed") 
    return df["Validation 20"]

@task
def validation_25(df):
    df["Validation 25"] = "" 
    condition1 =  (df["Analyte"].isin(ip_message_list)) & (df["TestResultFlags"].astype(str) =="A") # we might be too strict when looking at origin across the board.
    sampleID_list = df.loc[condition1]["SampleID"].unique() # this establishes which sampleIDs meet condition 1
    for sampleID in sampleID_list:
        sample_filter = (df["SampleID"] == sampleID)
        subset_df = df.loc[sample_filter]
        result_ID_list = subset_df.loc[condition1]["TestResultID"].to_list()
        analyte_to_check_list = df.loc[(sample_filter) &(condition1)]["Analyte"].astype(str).to_list() # should return a single result, NOT ALWAYS TRUE
        analyte_to_check_list = [ i+"?" if (("?" not in i) and (i!="PLT_Abn_Distribution")) else i  for i in analyte_to_check_list ]
        # analyte_to_check_list = [ i.replace("_"," ") if "_Lympho" in i else i for i in analyte_to_check_list ]
        record_dict = dict(zip(result_ID_list,analyte_to_check_list))
        for record_ID, analyte in record_dict.items():
            analyte_confirmed = analyte + " Confirmed?" 
            condition3 = np.any(np.where((subset_df["Analyte"].str.replace("_"," ") == analyte_confirmed.replace("_"," ")) & (subset_df["TestResultValue"].astype(str).isin(["Yes","No"])), True,False))
            df.loc[sample_filter & (df["TestResultID"] == record_ID),"Validation 25"]= np.where((condition3) ,"passed","Ip Message Test result is not flagged as confirmed")
    return df["Validation 25"]

@task
def validation_28_and_29(df):
    df["Validation 28"] = ""
    df["Validation 29"] = ""
    unique_sampleIDs = df["SampleID"].unique()
    for sampleID in unique_sampleIDs:
        sample_filter = (df["SampleID"] == sampleID)
        filtered_df = df.loc[sample_filter]
        found_method_list = filtered_df["Method"].to_list()
        check_cbc = any(item in found_method_list for item in cbc_list)
        check_chem = any(item in found_method_list for item in chem_list)
        
        if check_cbc & check_chem:
            print(sampleID,": found multiple panels")
        if check_cbc:
            cbc_bool = set(cbc_list).issubset(set(found_method_list))
            if cbc_bool:
                df.loc[sample_filter,"Validation 28"] ="passed"

                cbc_filter = (filtered_df["Method"].isin(cbc_list))
                cbc_df= filtered_df.loc[cbc_filter]
                if all(~is_number(cbc_df['TestResultValue'])):
                    all_same_bool = (cbc_df['TestResultValue'] == cbc_df['TestResultValue'].iloc[0]).all()
                    if all_same_bool:
                        df.loc[sample_filter & cbc_filter , "Validation 29"] = "passed"
                    else:
                        df.loc[sample_filter & cbc_filter , "Validation 29"] = "Strings should be the same across panel"

            else:
                missing_test = [i for i in cbc_list  if i not in found_method_list]
                df.loc[sample_filter,"Validation 28"] =f"Incomplete results in CBC panel. Missing :{missing_test}"
                
        elif check_chem:
            chem_bool =set(chem_list).issubset(set(found_method_list))
            tsh_bool =set(["TSH3UL","X3PFH"]).issubset(set(found_method_list))
            if chem_bool or tsh_bool :
                df.loc[sample_filter,"Validation 28"] ="passed"
                chem_filter = (filtered_df["Method"].isin(chem_list))
                chem_df= filtered_df.loc[chem_filter]
                if all(~is_number(chem_df['TestResultValue'])):
                    all_same_bool = (chem_df['TestResultValue'] == chem_df['TestResultValue'].iloc[0]).all()
                    if all_same_bool:
                        df.loc[sample_filter & chem_filter, "Validation 29"] = "passed"
                    else:
                        df.loc[sample_filter & chem_filter, "Validation 29"] = "Strings should be the same across panel"

            else:
                missing_test = [i for i in chem_list if i not in found_method_list]
                df.loc[sample_filter,"Validation 28"] =f"Incomplete results in Chem panel. Missing :{missing_test}"
    return df["Validation 28"],df["Validation 29"]


@task
def validation_33(df):  #takes df, returns validation 6 series
    df["Validation 33"] = "" 
    condition1 = ( df["Analyte"].str.contains("Confirmed?",na=False))
    sampleID_list = df.loc[condition1]["SampleID"].unique()
    for sampleID in sampleID_list:
        sample_filter = (df["SampleID"] == sampleID)
        ip_message = df.loc[sample_filter & condition1]["Analyte"].to_list()[0]
        ip_message_to_check = ip_message.split(" Confirmed?")[0]
        # if "_Lympho" in ip_message_to_check:
        #     ip_message_to_check = ip_message_to_check.replace(" ","_")
        record_ID = df.loc[sample_filter & condition1]["TestResultID"].to_list()[0]
        condition2 = np.any(np.where((df.loc[sample_filter]["Analyte"].str.replace("_"," ")) == ip_message_to_check.replace("_"," ") , True,False))
        df.loc[sample_filter  & (df["TestResultID"] == record_ID),"Validation 33"]= np.where((condition2) ,"passed","missing corresponding Records")
    return df["Validation 33"]

@task
def validation_36(df):
    df["Validation 36"] = ""
    unique_samples = df["SampleID"].unique()
    for sampleID in unique_samples:
        sample_filter = (df["SampleID"] == sampleID)
        sample_df = df.loc[(sample_filter)]
        tube_panel_dict = val_36_mapping.get(sampleID[0])
        tubeID_list = sample_df["Tube"].unique()
        for tube in tubeID_list:
            panel = tube_panel_dict.get(tube)
            if type(panel) == NoneType: # since we maybe have blank tube, or tube == "Slide" we want to skip those
                continue
            tube_filter = (sample_df["Tube"] == tube) & (~sample_df["Method"].isnull())
            found_methods = sample_df.loc[tube_filter]["Method"].to_list()

            all_found_bool = set(panel).issubset(set(found_methods))
            if all_found_bool:
                df.loc[sample_filter & tube_filter ,"Validation 36"]= "passed"
            else:
                missing_methods =  [i for i in panel if i not in found_methods]
                df.loc[sample_filter & tube_filter ,"Validation 36"]= f"Incomplete Tests. Missing: {missing_methods}"
    return df["Validation 36"]

def validation_37(df):
    df["Validation 37"] = ""
    condition1 = ((df["Analyte"].isin(ip_message_list)) & (df["TestResultFlags"].isnull()) &  (df["Repeat"] == "Y") & (df["InitialResult"].str.contains("A|W",na=False)))
    id_to_check = df.loc[condition1]["SampleID"].unique()
    for sampleID in id_to_check:
        sample_filter = (df["SampleID"] == sampleID)
        sample_df = df.loc[(sample_filter)]
        analytes = sample_df["Analyte"].to_list()
        comfirmed_bool = any(["Confirmed?" in i for i in analytes])
        ip_message_filter = df["Analyte"].isin(ip_message_list)
        df.loc[sample_filter & ip_message_filter,"Validation 37"]= np.where((comfirmed_bool) ,"passed","IP Message confirmation should be present")
    return df["Validation 37"]

@task  
def validation_38(df):
    df["Validation 38"] = ""
    condition1 = (df["Repeat"] == "Y") & (df["Origin"].isin(val_9_origin_values))
    sampleID_list = df.loc[condition1]["SampleID"].unique()
    for sampleID in sampleID_list:
        sample_filter = (df["SampleID"] == sampleID)
        condition2 = (df["Repeat"] != "Y")
        resultID_list = df.loc[sample_filter & condition1]["TestResultID"].to_list()
        aspiration_origin_list = df.loc[sample_filter & condition1][["AspirationTimestamp","Origin"]].values.tolist()
        record_dict = dict(zip(resultID_list,aspiration_origin_list))
        for resultID, timestamp_origin in record_dict.items():
            # test_comment_bool = df.loc[df["TestResultID"] == resultID]["Test Comments"].isnull().to_list()[0]
            cond_3_df = df.loc[condition2 & (df["Origin"] == timestamp_origin[1]) & sample_filter]
            condition3 = np.any(np.where((timestamp_origin[0] < cond_3_df["AspirationTimestamp"]),True, np.where((timestamp_origin[0] == cond_3_df["AspirationTimestamp"]),True,False)))
            df.loc[sample_filter & (df["AspirationTimestamp"] == timestamp_origin[0]) & (df["TestResultID"] == resultID),"Validation 38"]= np.where((condition3) ,"Aspiration Time of repeat test is not after initial tests","passed")        
    return df["Validation 38"]

@flow
def apply_validation_checks(df): #takes dataframe, returns dataframe with new validation columns with pass/failed reason.
                        # logic structure np.where(condition(s) , value returned if true, value returned if false)
    df["Validation 1"] = np.where((df["Analyte"].isin(val_1_analyte_list)==False) & (df["TestResultValue"].isnull()),"TestResultValue cannot be Null" , np.where((df["Analyte"].isin(val_1_analyte_list)) & (df["TestResultFlags"].isnull()==False) &(df["TestResultValue"].isnull()), "TestResultValue cannot be Null", "passed"))
    df["Validation 2"] = np.where((df["Repeat"] == "Y") & ((df["Test Comments"].isnull()) |  (df["Test Comments"].str.lower().str.contains("rerun|rejected",na=False) == False)), "Repeated Test Has No Comments or Comment does not contain 'rerun' or 'rejected'", "passed")
    df["Validation 3"] = np.where((df["Repeat"] == "Y") & (df["InitialResult"].isnull()), "Repeated Test Has no initial result","passed")
    df["Validation 4"] = np.where((df["Origin"].isin(val_4_origin_values)) & (df["AspirationTimestamp"].isnull()),"Missing Aspiration time on a valid result", "passed") 
    df["Validation 5"] = np.where((df["Origin"] == "Sysmex XN-1000") & (df["Analyte"].str.contains("\?",na=False)) &  (df["AspirationTimestamp"].isnull() ==False), np.where((df["Origin"] == "Sysmex XN-1000") & (df["Analyte"].str.contains("\?")) & (df["Test Comments"].isnull()) & (df["AspirationTimestamp"].isnull()==False),"Aspiration time should be null","passed") ,"passed")
    # more complex validtions get split into its own function
    df["Validation 6"] = validation_6(df)
    df["Validation 7"] = validation_7(df)
    df["Validation 8"] = np.where((df["Analyte"].isin(val_8_analyte_list)==False) & (df["Origin"].isin(val_8_origin_values))& (df["AspirationTimestamp"].isnull()), "Aspiration Time cannot be Null", "passed")
    df["Validation 9"] = validation_9(df)

    test_result_float = test_result_convert_to_float(df["TestResultValue"])
    df["Validation 10"] = np.where((df["Analyte"].astype(str) == "X3PFH") & (test_result_float.isnull() == False) & (test_result_float > 100) & (df["Repeat"] != "Y"), "PFH > AMR - repeated without correct documentation","passed")
    df["Validation 11"] = np.where((df["Analyte"] == "TRIG") & (test_result_float>550) & ((df["Repeat"] != "Y")) , "Triglycerides > AMR - repeated without correct documentation","passed")
    df["Validation 12"] = np.where((df["Tube"].isnull()), "Tube cannot be null","passed")
    df["Validation 13"] = np.where((df["Test Comments"].str.lower().str.contains("rerun", na=False)) & (df["Repeat"] != "Y"), "Test comment indicates that repeat should be 'Y'", "passed")
    df["Validation 14"] = np.where((df["Origin"] == sysmex) & (df["Analyte"].str.contains("\?|PLT_Abn_Distribution", na=False) == False) & (df["AspirationTimestamp"].isnull()),"Aspiration Timestamp should not be null","passed")
    
    duplicate_columns_to_check = df.columns.to_list()
    duplicate_columns_to_check.remove('TestResultID')
    duplicate_columns_to_check.remove('Origin')
    df["Validation 15"] = np.where((df.duplicated(subset=duplicate_columns_to_check, keep=False)) ,"Record is duplicated","passed")
    df["Validation 16"] = validation_16(df)


    ip_message_list_17 = [i  for i in ip_message_list if "Confirmed?" not in i]
    df["Validation 17"] = np.where((df["Analyte"].isin(ip_message_list_17)) &((df["Analyte"]!="PLTCLUMP")) &((df["Repeat"]!="Y"))& (df["TestResultFlags"].isnull()),"Test should not be present if TestResultFlag is null","passed")
    df["Validation 18"] = np.where((df["SampleID"].str.split("-").str[-1] == df["Tube"].astype(str)) | (df["Tube"].astype(str) == "Slide"), "passed", "Wrong order choice for tube type")
    # df["Validation 19"] = np.where((df["Repeat"]=="Y") & (~is_number(df["TestResultValue"].astype(str))) , "Repeat was not successful and needs correction in LIS", "passed")
    df["Validation 20"] = validation_20(df)
    df["Validation 21"] = np.where((df["Repeat"].isnull()) & (df["InitialResult"].isnull()==False),"Test Has initial result but not indicated as Repeat","passed")
    acceptable_string_list_22 = [i.lower() for i in acceptable_string_list]
    df["Validation 22"] = np.where((~is_number(df["TestResultValue"].astype(str))) & ((df["TestResultValue"].str.lower().isin(acceptable_string_list_22) == False) & (df["TestResultValue"].str.startswith(("<",">"),na=False)==False)),"Unacceptable String Value in TestResultValue","passed")
    acceptable_string_list_23 = [i.lower() for i in acceptable_string_list__23]
    # df["Validation 23"] = np.where((df["TestResultValue"].str.lower().isin(acceptable_string_list_23)) & ((df["Repeat"].isnull()==False) | (df["InitialResult"].isnull()==False)),"Repeat and Initial Result should be null","passed")
    df["Validation 24"] = np.where(((df["Origin"] == "Sysmex XN-1000")) & (df["Analyte"].str.contains("Fragments?",na=False) == False) & (df["TestResultFlags"].isin(["W","A"])) & (df["Repeat"] != "Y"),"Missing Repeat = 'Y'","passed")
    df["Validation 25"] = validation_25(df)
    df["Validation 26"] = np.where((df["Analyte"].isin(ip_message_list) == False) & ((df["Method"].isnull()) | (df["TestCloverCode"].isnull())),"Method and TestClover Code should not be null","passed")
    df["Validation 27"] = np.where((df["SampleID"].str[0] != df["StudyID"].str[-1]),"Data does not belong in the file","passed")
    df["Validation 28"],df["Validation 29"] = validation_28_and_29(df)
    df["Validation 30"] = np.where(df["Tube"].isnull(),"Tube cannot be null", "passed")
    df["Validation 31"] = np.where((df["SubjID"] != df["SampleID"].str.rsplit('-',1).str[0].str.replace("R","S")),"SubjectID does not match SampleID ", "passed")
    df["Validation 32"]= np.where((df["Method"].isnull()) & (df["Analyte"].str.contains("Confirmed?",na=False) == False)&(df["Analyte"].isin(ip_message_list) == False), "Analyte should have IP message", "passed")
    df["Validation 33"]= validation_33(df)
    df["Validation 34"]= np.where(((df["Repeat"] == "Y") & (df["Method"].isin(cbc_list))  & (df["InitialResult"].str.contains("W|----",na=False) == False)) , "Initial Result should contain 'W'", "passed")
    df["Validation 35"]= np.where(((df["Repeat"] == "Y") & (df["Analyte"].isin(ip_message_list)) & (df["InitialResult"].str.contains("A|----",na=False) == False)) , "Initial Result should contain 'A'", "passed")
    df["Validation 36"]= validation_36(df)
    df["Validation 37"]= validation_37(df)
    df["Validation 38"]= validation_38(df)


@task
def split_val_df_noted_records(df):
    filter = (df["Test Comments"].str.contains("NOTE:",na=False))
    noted_df = df.loc[filter]
    remaining_df = df.loc[~filter]

    return noted_df,remaining_df

@task
def write_report(output_path,worksheet_dict):
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        for sheetname, sheet_df in worksheet_dict.items():
            try:           
                    sheet_df.to_excel(writer, sheet_name= sheetname, index = False, header=True) 
                    auto_adjust_col_width(writer,sheetname,sheet_df)                   
            except Exception as e:
                print(e)
        print("Output Has Been Written")

@flow
def generate_report(df,output_path): #takes dataframe, writes excel output. 
    validation_columns = [i for i in df.columns if "Validation" in i]
    condition1 = df[validation_columns].isin(["","passed"]).all(axis=1)
    good_data = df.loc[(condition1)]
    bad_data = df.loc[(condition1==False)]  
    all_data = df
    # check_for_data_loss(good_data, bad_data, all_data, original_data)
    summary_df, columns_to_remove = data_quality_summary(good_data, bad_data, all_data,validation_columns)
    summary_df = summary_df.rename(index = {0:'Value'}).transpose().reset_index()
    summary_df.rename(columns={"index": "Check"},inplace=True)

    noted_df,bad_df = split_val_df_noted_records(bad_data)
    bad_df.drop(columns=columns_to_remove,inplace=True)
    worksheet_dict = {"Data Quality Summary":summary_df,"Failed Validation":bad_df,"Commented and Failed":noted_df,"Passed Validation":good_data,"All Records":all_data}
    write_report(output_path,worksheet_dict)

@task
def data_quality_summary(good_data, bad_data, all_data,validation_columns):
    summary_df= pd.DataFrame(index=range(1))
    good_count = len(good_data)
    bad_count = len(bad_data)
    all_count = len(all_data)
    summary_df["Total Passed Validation"] = good_count
    summary_df["Total Failed Validation"] = bad_count
    summary_df["Data Quality Score"] = round((good_count/all_count)*100, 3)
    columns_to_remove = []
    for val in validation_columns:
        values_list = all_data[val].to_list()
        failed = [i for i in values_list if i not in ["","passed"]]
        summary_df["Failed " +val] = len(failed)
        if len(failed) == 0:
            columns_to_remove.append(val)

    return summary_df, columns_to_remove

def auto_adjust_col_width(writer,sheet,df):
    for column in df:
        column_width = max(df[column].astype(str).map(len).max(), len(column))
        col_idx = df.columns.get_loc(column)
        writer.sheets[sheet].set_column(col_idx, col_idx, column_width)
            
def check_for_data_loss(good_data, bad_data, all_data, original_data):
    if ((len(bad_data)+len(good_data) != len(original_data)) |(len(original_data) != len(all_data))):
        print("Data loss occured, please check log file")

def read_excel_file(input):
    is_csv = input.endswith("csv")
    if is_csv:
        df = pd.read_csv(input, keep_default_na=False, na_values="")
    else:
        df = pd.read_excel(input, keep_default_na=False, na_values="")
    return df

# our global variables for condition checking
val_1_analyte_list = ["Atypical_Lympho?","PLT_Abn_Distribution","Left_Shift?","Fragments?"]
val_4_origin_values = ["Atellica1","Atellica2","BioRad D100"]
val_8_origin_values = ["Atellica1","Atellica2","BioRad D100","Sysmex XN-1000"]
val_9_origin_values = ["Atellica1","Atellica2","BioRad D100","Sysmex XN-1000"]
sysmex = "Sysmex XN-1000"
possible_nulls = ["", np.nan, "----", "NaN", None, np.datetime64('NaT'), "NaT"]

val_8_analyte_list = ["PLT_Abn_Distribution","Fragments?","Abn_Lympho?","ACTION_MESSAGE_Aged_Sample?","Atypical_Lympho?","Blasts?",
"Blasts/Abn_Lympho?","Dimorphic Population?","HGB_Defect?","Iron_Deficiency?","Left_Shift?",
"NRBC Present?","PLT_Clumps?","PRBC?","RBC_Agglutination?","Turbidity/HGB_Interference?"]

ip_message_list = ["WBC_Abn_Scattergram","RBC_Abn_Distribution","RBC_Agglutination?","PLT_Abn_Distribution", "PLT_Abn_Distribution Confirmed?",
"PLT_Abn_Scattergram","PLT_Clumps?","Blasts?","Blasts/Abn_Lympho?","Atypical_Lympho?","Atypical Lympho? Confirmed?","Blasts/Abn Lympho? Confirmed?","Blasts/Abn_Lympho? Confirmed?","Abn_Lympho?","Turbidity/HGB_Interference?",
"Left_Shift?","NRBC_Present","Iron_Deficiency?","Fragments?","Fragments? Confirmed?", "PLTCLUMP", "PLT_Clumps? Confirmed?"] 


# ip_message_list = ["WBC_Abn_Scattergram","RBC_Abn_Distribution","RBC_Agglutination?","PLT_Abn_Distribution",
# "PLT_Abn_Scattergram","PLT_Clumps?","Blasts?","Blasts/Abn_Lympho?","Atypical_Lympho?","Abn_Lympho?","Turbidity/HGB_Interference?",
# "Left_Shift?","NRBC_Present","Iron_Deficiency?","Fragments?", "PLTCLUMP"] 



# ip_confirmation_list = ["PLT_Clumps? Confirmed?","PLT_Abn_Distribution Confirmed?","Fragments? Confirmed?"
# ,"Atypical Lympho? Confirmed?", "Blasts/Abn Lympho? Confirmed?",Blasts? Confirmed]


val_16_analyte_dict = {'WBC':2, 'RBC':2,'HGB':1 ,'HCT':1,'MCV':1,'MCH':1,'MCHC':1,'RDW-SD':1,'RDW-CV':1,'PLT-I':0,'Neut%':1,
'Lymph%':1,'MONO%':1,'EO%':1,'BASO%':1,'ALB':2,'ALKP':0,'ALT':0,'AST':0,'BUN':0,'CA_2':1,'CHOL':0,'CL':0,'CO2':1,'CREA':2,
'GluH_3':0,'HDL':1,'K':2,'LDL':1,'NA':0,'TBIL':2,'TP':1,'TRIG':0,'TSH':3,'VITD':2,'X3PFH':3}

acceptable_string_list = ["No sample provided to Test", "Collection not attempted","No sample received","Unable to collect",
"Quantity not sufficient for repeat analysis","Quantity not sufficient for testing","Specimen hemolyzed",
"Test not performed due to special occurrence", "Test not Performed (Above fill line)","Error","Yes","No","Slight","Moderate","Marked","None Seen","A"]

acceptable_string_list__23 = ["A","No sample provided to Test", "Collection not attempted","No sample received","Unable to collect",
"Specimen hemolyzed","Test not performed due to special occurrence","Quantity not sufficient for testing","Test not Performed (Above fill line): When the tube was overfilled",
"Error","Yes","No","Slight","Moderate","Marked","None Seen"]

cbc_list = [
    "BASO%",
    "EOS%",
    "HCT",
    "HGB",
    "LYMPH%",
    "MCH",
    "MCHC",
    "MCV",
    "MONO%",
    "NEUT%",
    "PLT-I",
    "RBC",
    "RDW-SD",
    "RDW",
    "WBC"
]

chem_list = [
    "ALP_2C",
    "CA_2",
    "VitD",
    "CO2_c",
    "UN_c",
    "CL",
    "ECre_2",
    "D_HDL",
    "K",
    "Tbil_2",
    "Na",
    "Chol_2",
    "AlbP",
    "AST",
    "ALT",
    "TRIG",
    "GluH_3",
    "DLDL",
    "X3PFH",
    "TP"
]

val_36_mapping={
    "5":{
            "T01":["TSH3UL","X3PFH"],
            "T03":["TSH3UL","X3PFH"],
            "T02":chem_list+["X3PFH"],
            "T04":chem_list+["X3PFH"],
            "T05":chem_list+["X3PFH"],
            "T06":chem_list+["X3PFH"],
            "T07":cbc_list+["A1C"],
            "T08":cbc_list+["A1C"],
            "T09":cbc_list+["A1C"],
            "T10":cbc_list+["A1C"]
        },
    "6":{
            "T01":chem_list+["X3PFH"],
            "T02":chem_list+["X3PFH"],
            "T03":chem_list+["X3PFH"],
            "T04":chem_list+["X3PFH"],
            "T05":["TSH3UL","X3PFH"],
            "T06":["TSH3UL","X3PFH"],
            "T07":["TSH3UL","X3PFH"],
            "T08":["TSH3UL","X3PFH"],
            "T09":cbc_list+["A1C"],
            "T10":cbc_list+["A1C"],
            "T11":cbc_list+["A1C"],
            "T12":cbc_list+["A1C"],
        },
    "7":{
            "T01":chem_list+["X3PFH"],
            "T02":chem_list+["X3PFH"],
            "T03":chem_list+["X3PFH"],
            "T04":chem_list+["X3PFH"],
            "T05":chem_list+["X3PFH"],
            "T06":chem_list+["X3PFH"],
            "T07":chem_list+["X3PFH"],
            "T08":chem_list+["X3PFH"],
            "T09":chem_list+["X3PFH"],
            "T10":chem_list+["X3PFH"],
            "T11":chem_list+["X3PFH"],
            "T12":chem_list+["X3PFH"],
            "T13":chem_list+["X3PFH"],
            "T14":chem_list+["X3PFH"],
            "T15":chem_list+["X3PFH"],
            "T16":chem_list+["X3PFH"],
            "T17":chem_list+["X3PFH"],
            "T18":chem_list+["X3PFH"],
            "T19":chem_list+["X3PFH"],
            "T20":chem_list+["X3PFH"],
            "T21":chem_list+["X3PFH"],
            "T22":chem_list+["X3PFH"],
            "T23":chem_list+["X3PFH"],
            "T24":chem_list+["X3PFH"],
            "T25":cbc_list+["A1C"],
            "T26":cbc_list+["A1C"],
            "T27":cbc_list+["A1C"],
            "T28":cbc_list+["A1C"],
            "T29":cbc_list+["A1C"],
            "T30":cbc_list+["A1C"],
            "T31":cbc_list+["A1C"],
            "T32":cbc_list+["A1C"],
            "T33":cbc_list+["A1C"],
            "T34":cbc_list+["A1C"],
            "T35":cbc_list+["A1C"],
            "T36":cbc_list+["A1C"],
            "T37":cbc_list+["A1C"],
            "T38":cbc_list+["A1C"],
            "T39":cbc_list+["A1C"],
            "T40":cbc_list+["A1C"],
            "T41":cbc_list+["A1C"],
            "T42":cbc_list+["A1C"],
            "T43":cbc_list+["A1C"],
            "T44":cbc_list+["A1C"],
            "T45":cbc_list+["A1C"],
            "T46":cbc_list+["A1C"],
            "T47":cbc_list+["A1C"],
            "T48":cbc_list+["A1C"]
        },
    "9":{
            "T01":chem_list+["X3PFH"],
            "T02":chem_list+["X3PFH"],
            "T03":chem_list+["X3PFH"],
            "T04":chem_list+["X3PFH"],
            "T05":chem_list+["X3PFH"],
            "T06":chem_list+["X3PFH"],
            "T07":chem_list+["X3PFH"],
            "T08":chem_list+["X3PFH"],
            "T09":cbc_list+["A1C"],
            "T10":cbc_list+["A1C"],
            "T11":cbc_list+["A1C"],
            "T12":cbc_list+["A1C"],
            "T13":cbc_list+["A1C"],
            "T14":cbc_list+["A1C"],
            "T15":cbc_list+["A1C"],
            "T16":cbc_list+["A1C"]
        }
}


@flow
def process_lis_data(input_file_path,output_directory):
    input_file_name = os.path.basename(input_file_path)
    output_string = input_file_name.split(".")[0]
    date = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")
    output_file = f"\Validation Results for {output_string} {date}.xlsx"
    output_path = output_directory + "/" + output_file
    df = read_excel_file(input_file_path)
    original_data = df.copy()
    apply_validation_checks(df)
    generate_report(df,output_path)
        
@flow
def process_all(dir):

    input_directory = dir+"/input"
    output_directory= dir+"/output"
    fail_directory = dir+"/fail"
    success_directory = dir+"/success"

    for filename in os.scandir(input_directory):
        if filename.is_file():
            input_file_path =filename.path
            input_file_name = os.path.basename(input_file_path)
            
            state = process_lis_data(input_file_path,output_directory,return_state=True)

            if state.is_failed():
                shutil.move(input_file_path,(fail_directory +"/"+input_file_name))
                print((f"processing failed for {input_file_name}, sending to failed folder"))
            else:
                shutil.move(input_file_path,(success_directory +"/"+input_file_name))















