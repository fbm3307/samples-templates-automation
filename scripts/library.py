from email.mime import image
import os
from re import template
import re
import sys
from typing import final
from uuid import uuid4
from wsgiref import headers
import yaml
import requests
import argparse
from create_issue import *
from update_issue import *
import random
import time
import base64

parser = argparse.ArgumentParser()
parser.add_argument("--pr_url", help="Name of the yaml file which triggered this action")
parser.add_argument("--branch", help="Source branch from where PR is generated")
parser.add_argument("--src_repo", help="Source repo from where PR is generated")
args = parser.parse_args()

pr_url = args.pr_url
source_branch = args.branch
src_repo = args.src_repo
print("Received Data: ", pr_url)
print("Source Repo : ", src_repo)
gFilename = "" # This will be used whie updating the issue.
gMessageId = "" # This variable will store the message id (either newly generated or previously generated)
MAX_RANDOM = 1000000
VALID_OPERATIONS = ["create_issues", "comment", "close_issues"]
VALID_RECEPIENT_TYPE = ["testtemplates", "testimagestreams", "testall","templates", "imagestreams", "all"]
PR_MERGE_COMMIT_TITLE = "Merging through workflow [skip action]"
PR_MERGE_COMMIT_MESSAGE = "Merging through workflow [skip action]"

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

imageStreamDict = {}
templateDict = {}
combinedDict = {}
testimagestreamsDict = {"testimage":["fbm3307/test-learn"], "testimagest":["fbm3307/testimagestreams1"]}
testtemplatesDict = {"testtemplate":["fbm3307/testtemplates"], "testimage":["fbm3307/test-learn"]}
testallDict = {}


def load_openshift_yaml():
    global imageStreamDict
    global templateDict
    global combinedDict

    print("Loading the repo list from official.yaml")

    LIBRARY_FILE= requests.get("https://github.com/openshift/library/blob/master/official.yaml?raw=true")
    filedata = yaml.safe_load(LIBRARY_FILE.text)
    githubcontent=filedata["data"]
    
    for reponame in githubcontent:
        imagestreamLocationSet = set() #Initialize the locationSet
        if("imagestreams" in githubcontent[reponame]):
            #code for imagestream
            for ele in githubcontent[reponame]["imagestreams"]:
                location = ele["location"]
                temp = (str(location).split("//")[1]).split("/")
                repo1,repo2 = temp[1], temp[2]
                finalUrl = f"{str(repo1)}/{str(repo2)}"
                imagestreamLocationSet.add(finalUrl)
            imageStreamDict[reponame] = list(imagestreamLocationSet)
        templateLocationSet = set() #Re-Initialize the location list
        if("templates" in githubcontent[reponame]):
            #code for templates
            for ele in githubcontent[reponame]["templates"]:
                location = ele["location"]
                temp = (str(location).split("//")[1]).split("/")
                repo1,repo2 = temp[1], temp[2]
                finalUrl = f"{str(repo1)}/{str(repo2)}"
                templateLocationSet.add(finalUrl)
            templateDict[reponame] = list(templateLocationSet)
        imagestreamLocationSet.update(templateLocationSet)
        combinedDict[reponame] = list(imagestreamLocationSet)
    print("completed the division of the  repos into imagestreams and templates")

def load_yaml_test():
    global testimagestreamsDict
    global testtemplatesDict
    global testallDict

    print("Loading the test repo list")
    for key in testimagestreamsDict.keys():
        if(key not in testallDict):
            testallDict[key] = testimagestreamsDict[key]

    for key in testtemplatesDict.keys():
        if(key not in testallDict):
            testallDict[key] = testtemplatesDict[key]
    
def target_repos(user_input="", issueTitle="", issueDescription=""):
    if(user_input == ""):
        return False
    output = [] # output = {repo_url:issue_id_url}
    targetDict = {}
    if(user_input == "templates"):
        targetDict = templateDict
        print("Going to create the issue in Template target repos")
    elif(user_input == "imagestreams"):
        targetDict = imageStreamDict
        print("Going to create the issue in Imagestreams target repos")
    elif(user_input == "all"):
        targetDict = combinedDict
        print("Going to create the issue in All repos")
    elif(user_input == "testimagestreams"):
        targetDict = testimagestreamsDict
        print("Going to create the issue in Testimagestreams target repos")
    elif(user_input == "testtemplates"):
        targetDict = testtemplatesDict
        print("Going to create the issue in TestTemplate target repos")
    elif(user_input == "testall"):
        targetDict = testallDict
        print("Going to create the issue in TestAll repos")
    else:
        print("Invalid input")
        exit()
    return targetDict
    
def read_yml_file(file_url=""):
    try:
        headers = {'Accept': 'application/vnd.github.v3+json'}
        response = requests.get(file_url, headers=headers)
        response = response.json()
        file_content = response["content"]
        file_content = base64.b64decode(file_content)
        return file_content
    except Exception as e:
        print("error : " + str(e))
        return ""

def get_yaml_from_pr(pr_url=""):
    sample_msg_file_content = ""
    filename = ""
    try:
        pr_file_url = pr_url + "/files"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        pr_files = requests.get(pr_file_url, headers=headers)
        files = pr_files.json()
        for file in files:
            filename = file["filename"]
            validFile = filename.startswith("message/") and filename.endswith(".yml")
            if(not validFile):
                continue
            raw_url = file['raw_url']
            sample_msg_file_content = requests.get(raw_url, headers=headers).text
            #print("File Content : ", sample_msg_file_content)
            break
        return [sample_msg_file_content,filename]
    except Exception as e:
        print("error : " + str(e))
        return ["",""]

def create_issues_target(target="",issueTitle="", issueDescription=""):
    repos = target_repos(user_input=target)
    output=[]
    for repoName in repos.keys():
        repoList = repos[repoName]
        print("Initiating creation of issues in Repos : ", repoList)
        for repo in repoList:
            result = create_an_issue(title=issueTitle,description=issueDescription, repo=str(repo))
            if(result == False):
                print("Error while creating the issue in :", repo)
            else:
                issue_url = result[1]
                output.append(issue_url)
                print("Issue created successfully :", result[1])
    return output

def main():
    '''
    Execution Steps:
    1. Load the yaml file to fetch all the repo - load_openshift_yml()
    2. Parse PR body. Check with necessary conditions.
    3. Once parsed, call the appropriate functions and execute the steps.
    '''
    # Uncomment below once in Production
    load_openshift_yaml()
    load_yaml_test() # This is test function.
    print("Loaded OpenShift yaml file")
    # Code block for sample message file
    [sample_msg_file_content, filename] = get_yaml_from_pr(pr_url=pr_url)
    if(sample_msg_file_content=="" or filename == ""):
        print("sample_msg_file_content : ", sample_msg_file_content)
        print("filename : ", filename)
        print("Unable to extract the content from PR.")
        print("Exiting now")
        sys.exit()
    #  Code block for state message file
    base_url = str(pr_url.split("/pulls")[0])
    msg_id_list = []

    # Parse the yaml content which we got from PR
    try:
        sample_msg_yml_format = yaml.safe_load(sample_msg_file_content)
    except Exception as e:
        print("Not valid yaml content")
        print("Exiting now")
        sys.exit()

    if("recepient_type" not in sample_msg_yml_format):
        print("Recepient Type not found")
    else:
        recepient_type = sample_msg_yml_format["recepient_type"]
        if(recepient_type not in VALID_RECEPIENT_TYPE):
            print("Invalid recepient type : " + str(recepient_type) + ". Exiting Now!")
            sys.exit()

    if("msg-id" not in sample_msg_yml_format):
        # If msg-id is not in sample-msg.yml file, we will treat that as 'create_issue' task
        print("[+] No msg-id in the file. Creating issues!")
        if("title" not in sample_msg_yml_format):
            print("Could not find the title. Exiting Now!")
            sys.exit()
        elif("description" not in sample_msg_yml_format):
            print("Could not find the description. Exiting Now!")
            sys.exit()
        
        title = sample_msg_yml_format["title"]
        description = sample_msg_yml_format["description"]
        if(title == ""):
            print("Found empty title. Exiting Now!")
            sys.exit()
        if(description == ""):
            print("Found empty description. Exiting Now!")
            sys.exit()
        # Now, call create_issue(recepient_type="", title="", description=""). This will return [repo-url, issue-url]
        issue_dict = {}
        if(recepient_type == "testall"):
            issue_url_list = create_issues_target(target="testall", issueTitle=title, issueDescription=description)
            issue_dict["testall"] = issue_url_list
            issue_url_list = []
        elif(recepient_type == "testtemplates"):
            issue_url_list = create_issues_target(target="testtemplates", issueTitle=title, issueDescription=description)
            issue_dict["testtemplates"] = issue_url_list
            issue_url_list = []
        elif(recepient_type == "testimagestreams"):
            issue_url_list = create_issues_target(target="testimagestreams", issueTitle=title, issueDescription=description)
            issue_dict["testimagestreams"] = issue_url_list
            issue_url_list = []
        elif(recepient_type == "all"):
            issue_url_list = create_issues_target(target="all", issueTitle=title, issueDescription=description)
            issue_dict["all"] = issue_url_list
            issue_url_list = []
        elif(recepient_type == "templates"):
            issue_url_list = create_issues_target(target="templates", issueTitle=title, issueDescription=description)
            issue_dict["templates"] = issue_url_list
            issue_url_list = []
        elif(recepient_type == "imagestreams"):
            issue_url_list = create_issues_target(target="imagestreams", issueTitle=title, issueDescription=description)
            issue_dict["imagestreams"] = issue_url_list
            issue_url_list = []
        else:
            print("Could not find recepient_type. Exiting Now!")
            sys.exit()
        if(issue_dict == {}):
            print("Did not find any issues to update. Exiting Now!")
            sys.exit()
        
        # Now, we have to update sample-msg.yml with msg-id, and update state-msg.yml file with msg-id:issue-url
        msg_id = str(int(time.time()))
        # Now, append sample-msg.yml file
        sample_msg_file_content +="\nmsg-id: " + str(msg_id)
        print("Updating sample-msg.yml file")
        fileurl = "https://api.github.com/repos/" + str(src_repo) + "/contents/" + str(filename) + "?ref=" + str(source_branch)
        #fileurl = str(pr_url.split("/pulls")[0]) + "/contents/" + str(filename) + "?ref=" + str(source_branch)
        print("File being udpated : " + str(fileurl))
        if(update_file(filename=fileurl, content=sample_msg_file_content)):
            print("Updated sample-msg.yml file successfully!")
        else:
            print("Could not update sample-msg.yml file. Exiting Now!")
            sys.exit()
        
        # Once we are here, sample-msg.yml file should be in correct format.
        # Now, update state-msg.yml file with msg-id and issue-url.
        state_msg_url = "https://api.github.com/repos/" + str(src_repo) + "/contents/state" + "/" + str(msg_id) + ".yml" + "?ref="+str(source_branch)
        #state_msg_url = base_url + "/contents/state" + "/" + str(msg_id) + ".yml" + "?ref="+str(source_branch)
        print("URL generated for state file  : " + str(state_msg_url))
        headers = {'Accept': 'application/vnd.github.v3+json'}
        #state_file_content = requests.get(state_msg_url, headers=headers).text
        for issue_list in issue_dict:
            for issue in issue_dict[issue_list]:
                msg_id_list.append(issue)
        print("[+] Issues added to msg_id_dict")
        print("[+] msg_id_list : ", msg_id_list)
        print("[+] Generating the content for state_msg_file")
        state_file_content = ""
        for issue_url in msg_id_list:
            state_file_content += "- " + str(issue_url) + "\n"
        state_file_content = state_file_content[:-1]
        print("state_msg_file content generated", state_file_content)
        if(create_file(filename=state_msg_url, content=state_file_content)):
            print("Updated state-msg.yml file")
        else:
            print("Unable to updated state-msg.yml file")    
    elif("close" in sample_msg_yml_format):
        msg_id = sample_msg_yml_format["msg-id"]
        close = sample_msg_yml_format["close"]
        close = str(close).lower()
        if(close != "true"):
            print("[-] Invalid value for close operation : " + str(close) + ". Exiting Now!")
            sys.exit()
        print("[+] Looking for message id : " + str(msg_id))
        state_msg_url = base_url + "/contents/state/" + str(msg_id) + ".yml?ref=main"
        state_msg_content = read_yml_file(file_url=state_msg_url)
        if(state_msg_content == ""):
            print("[-] No file with given msg_id found. Exiting now!")
            sys.exit()
        state_msg_content_yml = yaml.safe_load(state_msg_content)
        issue_list = state_msg_content_yml # Adding extra varible for clarity purpose
        for issue in issue_list:
            repo = str(issue).split("https://github.com/")[1]
            repo = str(repo)
            issue_url = "https://api.github.com" + "/repos/" + repo
            isCloseSuccess = closeIssue(issue_url=issue_url)
            if(isCloseSuccess):
                print("[+] Closed Issue : " + str(issue))
            else:
                print("[-] Could not close the issue : " + str(issue))
                print("[-] Issue URL " + str(issue_url))
        print("[+] All issues closed.")
    elif("comment" in sample_msg_yml_format):
        comment = sample_msg_yml_format["comment"]
        if(comment == []):
            print("[-] Found empty comment. Exiting Now.")
            sys.exit()
        last_comment = comment[-1]
        msg_id = sample_msg_yml_format["msg-id"]
        print("[+] Looking for message id : " + str(msg_id))
        state_msg_url = base_url + "/contents/state/" + str(msg_id) + ".yml?ref=main"
        state_msg_content = read_yml_file(file_url=state_msg_url)
        if(state_msg_content == ""):
            print("[-] No file with given msg_id found. Exiting now!")
            sys.exit()
        # Once you are here, you will have the msg_id and the comment to be updated.
        state_msg_content_yml = yaml.safe_load(state_msg_content)
        issue_list = state_msg_content_yml # Adding new varible for better understanding
        for issue in issue_list:
            repo = str(issue).split("https://github.com/")[1]
            repo = str(repo)
            issue_url = "https://api.github.com" + "/repos/" + repo + "/comments"
            isCommentAdded = addComment(issue_url=issue_url, comment=last_comment)
            if(isCommentAdded):
                print("[+] Comment added for issue  : " + str(issue))
            else:
                print("[-] Could not add comment for the issue  : " + str(issue))
        print("[+] Comments added for all issues.")
    else:
        print("Could not find operation  Exiting Now!")
        sys.exit()
    # Merget the Pull Request
    print("[+] Initiating the merge of pull request")
    print("[+] Sleeping for 5 sec to ensure commits are updated.")
    time.sleep(5)
    isMerged = merge_pull_request(pr_url=pr_url, commit_title=PR_MERGE_COMMIT_TITLE, commit_message=PR_MERGE_COMMIT_MESSAGE)
    if(isMerged):
        print("[+] Merge successfull!")
    else:
        print("[-] Could not merge the request.")

# File execution starts from here
main()