import requests
import json
import re
import base64
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
import odoorpc as rpc
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor


_logger = logging.getLogger(__name__)
datetime_format = "%Y-%m-%dT%H:%M:%S.%fZ"
user = "daiduongnguyen2709@gmail.com"
password = "duong2709"
http_method = "https"
odoo_host = "anzgroup.viindoo.cloud"
odoo_db = "b9f8llbgoaoy"
maximum_project_proceed = 1

"""Login hệ thống odoo"""
odoo = rpc.ODOO(odoo_host, protocol='jsonrpc+ssl', port=443)
odoo.login(db=odoo_db, login=user, password=password,)

disable_warnings(InsecureRequestWarning)

headers={
    "Content-type": "application/json",
    "Authorization":"bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJVc2VySWQiOjgxMTY4LCJFbWFpbCI6InRodXkubmd1eWVuQGFuemdyb3VwLm9ubGluZSIsIk1vYmlsZSI6Iis4NDk3NjU4MzMyOSIsIlVzZXJOYW1lIjoiVGjhu6d5IE5ndXnhu4VuIiwiRGV2aWNlSWQiOiJlOWY3YmJlZi1iNzcwLTRhN2ItODAzMC00NzhiOGM5ZTEyYmYiLCJpYXQiOjE2OTY2NTQ4MzksImV4cCI6MTcwNDQzMDgzOX0.rMMNX2UK_bJ6JizEN07bGWMI-lZftZc1XWR1VwdHskk"
}

def get_record_set(model, search_domain, limit=None):
    return odoo.env[model].browse(odoo.env[model].search(search_domain, limit=limit))

"""Tạo user"""
# Get xteam users
use_request_url = "https://apiv2.myxteam.com/users/getRelativeUsers"
params = {'Workspace': 13109}
req = requests.post(
        use_request_url,
        headers=headers,
        params=params,
        verify=False
    )
# star creating user
mapped_xteam_user_fields = {
    "name": "UserName",
    "email": "Email",
    "login": "Email",
    "UserId": "UserId"
}
user_vals_list = []
user_vals_list_copy = [{'name': 'Thủy Nguyễn', 'email': 'thuy.nguyen@anzgroup.online', 'login': 'thuy.nguyen@anzgroup.online', 'UserId': 81168}]
result = json.loads(req.text)
for vals in result.get('data', []):
    filtered_vals = {}
    filtered_vals1 = {}
    for odoo_field, xteam_field in mapped_xteam_user_fields.items():
        if xteam_field in vals:
            filtered_vals[odoo_field] = vals[xteam_field]
            filtered_vals1[odoo_field] = vals[xteam_field]
    if filtered_vals:
        user_vals_list.append(filtered_vals)
        user_vals_list_copy.append(filtered_vals1)
print(user_vals_list)
OdooUser = odoo.env["res.users"]
OdooBotUser = get_record_set("res.users", [("name", "like", "admin")], limit=1)
odoo_users = get_record_set("res.users", [("login", "=", "thuy.nguyen@anzgroup.online")])

"""Tạo Task"""
tasks = False
mapped_xteam_task_fields = {
    "name": "TaskName",
    "user_ids": "AssignedId",
    "description": "Description",
    "create_uid": "OwnerId",
    "stage_id": "IsCompleted",
    "project_id": "ProjectId",
    "display_project_id": "ProjectId",
    "active": "IsArchived", # bool value
    "priority": "IsPin", # bool value
    "kanban_state": "IsLock", # bool value
    "is_blocked": "IsLock", # bool value
    "date_deadline": "DueDateUnix", # timestamp
    "create_date": "CreateDateUnix", # timestamp
    "date_end": "CompleteDateUnix", # timestamp
}
task_by_project_url = "https://apiv2.myxteam.com/tasks/getTasks"
task_url = "https://apiv2.myxteam.com/tasks/getTask"
subtask_url = "https://apiv2.myxteam.com/tasks/getSubTasks"
task_file_url = "https://apiv2.myxteam.com/Files/getTaskFiles"
tasks_comments_url = "https://apiv2.myxteam.com/tasks/getComments"
tasks_followers_url = "https://apiv2.myxteam.com/tasks/getTaskFollowers"
IrAttachment = odoo.env["ir.attachment"]
task_vals_list = []
xteam_task_ids = []
created_xteam_tasks_ids = []
created_xteam_projects_ids = []
mapped_users = {}
print("created tasks: ", len(created_xteam_tasks_ids))
new_partners = {"test_partner": "123"}
def replace_user(match):
    username = match.group(1)
    user_partner_id = match.group(2)
    domain = http_method + "://" + odoo_host
    return f'<a href="{domain}/web#model=res.partner&id={user_partner_id}" class="o_mail_redirect" data-oe-id="{user_partner_id}" data-oe-model="res.partner" target="_blank">@{username}</a>'

def _prepare_message_comment_by_task(xteam_task_id):
    def _xteam_comment_body_transform_into_odoo_comment(content):
        # body content transformation
        # We are going to transform "@[huyen.ta](userid:82011) Hello @[john.doe](userid:12345)"
        # into <a href="http://localhost:8015/web#model=res.partner&id=82011" class="o_mail_redirect" data-oe-id="82011" data-oe-model="res.partner" target="_blank">
        # @huyen.ta</a> Hello <a href="http://localhost:8015/web#model=res.partner&id=12345" class="o_mail_redirect" data-oe-id="12345" data-oe-model="res.partner" target="_blank">@john.doe</a>
        pattern1 = r'\@\[(.*?)\]\(userid:(\d+)\)'
        # Use re.sub to replace the matched text with the desired format
        transformed_text = re.sub(pattern1, replace_user, content)

        return transformed_text

    pattern = r'\(userid:(\d+)\)'
    comments_vals_list = []
    comments_by_task_params = {'TaskId': xteam_task_id, 'GetAll': True}
    comments_by_task_req = requests.post(
        tasks_comments_url,
        headers=headers,
        json=comments_by_task_params,
        verify=False
    )
    comments_by_task_result = {}
    if comments_by_task_req.status_code == 201 and comments_by_task_req.text:
        comments_by_task_result = json.loads(comments_by_task_req.text)
    # print("Comments Vals for task %s: " %(str(xteam_task_id)), comments_by_task_result)
    if comments_by_task_result.get("data", []):
        for comment_vals in comments_by_task_result.get("data", []):
            partner_ids = []
            # login_email = get_login_email_by_xteam_user_id(comment_vals["UserId"])
            author_user_id = mapped_users.get(comment_vals["UserId"], OdooBotUser.id)
            author_partner_id = False
            author_name = comment_vals.get("User", {}).get("UserName", False)
            if author_user_id:
                author_user = odoo.env["res.users"].browse(author_user_id)
                author_partner_id = author_user.partner_id.id
            else:
                if author_name:
                    if comment_vals["UserId"] in list(new_partners.keys()):
                        author_partner_id =  new_partners[comment_vals["UserId"]]
                    else:
                        new_partner_id = odoo.env["res.partner"].search([('name', '=', comment_vals.get("User", {}).get("UserName", "Anonymous"))], limit=1)
                        new_partner_id = new_partner_id[0] if new_partner_id else odoo.env["res.partner"].create({"name": comment_vals.get("User", {}).get("UserName", "Anonymous")})
                        new_partners[comment_vals["UserId"]] = new_partner_id
                        author_partner_id = new_partner_id
                else:
                    author_partner_id = OdooBotUser.partner_id.id
            xteam_user_ids = re.findall(pattern, comment_vals.get("Content", ""))
            # print("xteam_user_ids for content %s : " %(comment_vals.get("Content", "")), xteam_user_ids)
            body = _xteam_comment_body_transform_into_odoo_comment(comment_vals.get("Content", ""))
            if xteam_user_ids:
                for xteam_user_id in xteam_user_ids:
                    odoo_user_id = mapped_users.get(xteam_user_id, OdooBotUser.id)
                    if odoo_user_id:
                        odoo_user = odoo.env["res.users"].browse(odoo_user_id)
                        partner_ids.append(odoo_user.partner_id.id)
                        body = body.replace(xteam_user_id, str(odoo_user.partner_id.id))
            comments_vals_list.append({
                "author_id": author_partner_id,
                "body": body,
                "partner_ids": partner_ids,
            })
    return comments_vals_list

def get_login_email_by_xteam_user_id(user_id):
    """
    Return the email for login field of odoo
    in order to filtered for odoo_users variable above
    """
    lst = [item for item in user_vals_list_copy if item.get("UserId") == user_id]
    if lst:
        return lst[0].get("login", "")
    return ""


"""Tạo project task stage cho đống project"""
TaskStage = odoo.env["project.task.type"]
task_stage_new = TaskStage.browse(127)
task_stage_done = TaskStage.browse(120)

"""Tạo Project"""
# Get Teams
team_request_url = "https://apiv2.myxteam.com/teams/getTeams"
params = {'WorkspaceId': 13109}
req = requests.post(
                team_request_url,
                headers=headers,
                params=params,
                verify=False
            )
result = json.loads(req.text)
team_ids = []
for vals in result.get("data", []):
    team_ids.append(vals.get("TeamId", False))
print("Team ids: ", team_ids)
# Get Project by Teams
project_by_teams_request_url = "https://apiv2.myxteam.com/projects/getProjectsByTeams"
project_members_url = "https://apiv2.myxteam.com/projects/getProjectMembers" # để điền follower cho Mỗi dự án
params = {'TeamIds': team_ids}
project_ids = []
req = requests.post(
                project_by_teams_request_url,
                headers=headers,
                json=params,
                verify=False
            )
result = json.loads(req.text)
for vals in result.get("data", []):
    project_ids.append(vals.get("ProjectId", False))
print("Project Ids: ", project_ids)








# Get Project
projects = odoo.env["project.project"]
mapped_xteam_project_fields = {
    "name": "ProjectName",
    "user_id": "OwnerId",
    "description": "Description",
    "date_start": "StartDate",
    "date": "DueDate",
    "privacy_visibility": "IsPublic",
    "create_date": "CreateDate",
    "write_date": "UpdateDate",
    "create_uid": "OwnerId"
}
project_url = "https://apiv2.myxteam.com/projects/getProject"
project_vals_list = []

project_ids = [
    203325, 203326, 203328, 203329, 203331, 203333, 203340, 203497, 203508, 203518, 203523, 203804, 203867, 204340,
    204500, 204502, 204507, 204533, 204549, 204805, 204944, 204962, 204967, 205006, 205066, 205083, 205569, 205583, 205903, 205904, 205905,
    205906, 205916, 206317, 206318, 206319, 206321, 206323, 206326, 206344, 206475, 206597, 206647, 206890, 206898, 206920, 206924, 206926,
    206930, 207011, 207028, 207029, 207035, 207036, 207038, 207039, 207531, 207569, 208114, 208128, 208537, 208541, 208840, 209529, 209713,
    209779, 209972, 210505, 210507, 210564, 210578, 210579, 211405, 211460, 211861, 211862, 211863, 211864, 211866, 212227, 212300, 212420,
    212667, 213153, 213609, 215332, 215696, 216870, 218534, 219063, 219073, 220500, 221054, 221977, 222025, 223334, 223341, 223656, 223658,
    223660, 223970, 224647, 225874, 226552, 226682, 229092, 232068, 233056, 233190, 237145, 239089, 239818, 239838, 239869, 239963, 240561,
    240793, 240794, 240798, 241044, 242816, 243493, 243833, 244004, 245970, 246036, 247068, 247265, 247565, 247861, 248651, 248652, 248656,
    248980, 249002, 249003, 249037, 249038, 249149, 249151, 249469, 250132, 250752, 250929, 251728, 252086, 252394, 252525, 253129, 253938,
    254436, 255580, 255795, 256517, 256952, 257138, 257391, 259664, 260245, 260798, 261159, 261161, 261354, 261367, 261830, 262183, 262295,
    262577, 263081, 263234, 263809, 263920, 264442, 264453, 264619, 264620, 264621, 264633, 264634, 265391, 265663, 266257, 266266, 266785,
    266798, 267206, 267927, 267955, 268506, 270689, 270719, 272797, 272977, 274922, 274924, 274926, 275526, 276683, 277425, 277528, 278177,
    278385, 278497, 278502, 278776, 278846, 279002, 279684, 281167, 281177, 281381, 281800, 281804, 281821, 282069, 282351, 294671, 296344,
    296672, 297996, 298777, 303520, 304025, 304160, 304482, 305301, 306091, 306390, 308423, 309178, 310006, 311250, 328109, 329621, 332700,
    336783, 338748, 338952, 338954, 338955, 339281, 339335, 339343, 340351, 341545, 342541, 343942, 343947, 345506, 345614, 348571, 349543,
    353326, 353425, 355085, 355943, 357160, 359196, 359245, 359733, 371569, 371578, 371580, 380273, 383483, 383830, 384492, 392409, 395662,
    395663, 396237, 396775, 435168, 436309, 436790, 442051, 442974, 456166, 456167, 456452, 456454, 456457, 456465, 456466, 456477, 456478,
    456480, 456481, 456523, 458702, 459644, 471886, 472028, 473725, 476418, 477934, 481197, 483783, 486022, 486047, 486086, 486088, 486124,
    486126, 488372, 489222, 493447, 495887, 497729, 498005, 498346, 504607, 504925, 505668, 506932, 506967, 510057, 517549, 517804, 519125,
    519219, 519220, 522650, 529054, 544985, 546011, 547650, 549022, 551140, 551463, 552206, 553234, 557886, 559119, 560945, 563395, 565137,
    565165, 566221, 567338, 567598, 567599, 570873, 572235, 576041, 576505, 576865, 579627, 579890, 585045, 586952, 591314, 592011, 592074,
    592214, 592216, 592244, 592774, 592775, 593313, 593317, 593318, 593692, 593700, 595926, 596565, 596671, 597230, 601406, 602648, 606789,
    608311, 609719, 610976, 613042, 623518, 624049, 624957, 625787, 625788, 626024, 626025, 626026, 626027, 626032, 627153, 629617, 629853,
    632881, 637334, 638031, 638434, 638554, 638648, 638795, 642535, 643335, 648216, 648578, 652627, 653222, 653660]
created_projects = {}
#created_tasks = odoo.env["project.task"].search_read([('x_myxteam_task_id', '!=', False)], ['id', 'x_myxteam_task_id'])
created_tasks = {} #{a['x_myxteam_task_id']: a['id'] for a in created_tasks}
executor = ThreadPoolExecutor(max_workers=16)
for xteam_project_id in [653660]:#project_ids:
    odoo_project_id = xteam_project_id
    print("Xteam projects ids already created: ", xteam_project_id)
    # test_project = get_record_set("project.project", [("name", "=", "B2.16 - HỢP ĐỒNG KINH TẾ")]) for testing purpose
    try:
        task_by_project_params = {'ProjectId': xteam_project_id, 'IsArchived': False}
        task_by_project_params1 = {'ProjectId': xteam_project_id, 'IsArchived': True}
        task_by_project_req1 = requests.post(
                task_by_project_url,
                headers=headers,
                json=task_by_project_params,
                verify=False
            )
        task_by_project_result1 = {}
        if task_by_project_req1.status_code == 201 and task_by_project_req1.text:
            task_by_project_result1 = json.loads(task_by_project_req1.text)
        task_by_project_req2 = requests.post(
                task_by_project_url,
                headers=headers,
                json=task_by_project_params1,
                verify=False
            )
        task_by_project_result2 = {}
        if task_by_project_req2.status_code == 201 and task_by_project_req2.text:
            task_by_project_result2 = json.loads(task_by_project_req2.text)
        # print("Task by project result (not archived) for project_id %s: " %(str(xteam_project_id)), task_by_project_result1)
        # print("Task by project result (archived) for project_id %s: " %(str(xteam_project_id)), task_by_project_result2)
        task_by_project_results = task_by_project_result1.get("data", []) + task_by_project_result2.get("data", [])
        if task_by_project_results:
            for task_by_project_vals in task_by_project_result1.get("data", []) + task_by_project_result2.get("data", []):
                task_id = int(task_by_project_vals.get("TaskId", False))
                if not task_id:
                    print('task khong ton tai')
                    continue
                if task_id in created_tasks:
                    print('task da ton tai')
                    continue
                def _sync_task(task_by_project_vals, project_id, anz_project_id):
                    task_id = task_by_project_vals.get("TaskId", False)
                    print("starting task: ", task_id)
                    if not task_id:
                        print('task khong ton tai1')
                        return
                    if task_id in created_xteam_tasks_ids:
                        print('task khong ton tai2')
                        return
                    # if task_id != 7928219: for testing purpose
                    #     continue
                    xteam_task_ids.append(task_id)
                    # Perform get detail task
                    task_req = requests.post(
                        task_url,
                        headers=headers,
                        json={"TaskId": task_id},
                        verify=False
                    )
                    task_result = json.loads(task_req.text)
                    task_vals = task_result["data"]
                    # print("Detail task vals for task_id %s: " %(str(task_id)), task_vals)
                    # Perform get subtask
                    sub_task_req = requests.post(
                        subtask_url,
                        headers=headers,
                        json={"TaskId": task_id},
                        verify=False
                    )
                    sub_task_vals = []
                    if sub_task_req.status_code in( 201, 200) and sub_task_req.text:
                        sub_task_result = json.loads(sub_task_req.text)
                        sub_task_vals = sub_task_result.get("data", [])
                        
                        if not sub_task_vals:
                            print('k co substask1')
                            sub_task_vals = []
                        else:
                            print('co substask')
                    else:
                        print('khong co subtask')
                    # print("Sub task vals for task_id %s: " %(str(task_id)), sub_task_vals)
                    task_filtered_vals = {}
                    for odoo_field, xteam_field in mapped_xteam_task_fields.items():
                        if xteam_field in task_vals:
                            if xteam_field == "OwnerId":
                                xteam_user_id = task_vals["OwnerId"]
                                odoo_user_id = mapped_users.get(xteam_user_id, OdooBotUser.id)
                                task_filtered_vals[odoo_field] = odoo_user_id if odoo_user_id else 1
                            elif xteam_field == "AssignedId" and task_vals.get("AssignedId", False):
                                xteam_user_id = task_vals["AssignedId"]
                                odoo_user_id = mapped_users.get(xteam_user_id, OdooBotUser.id)
                                task_filtered_vals[odoo_field] = [odoo_user_id] if odoo_user_id else False
                            elif xteam_field == "IsCompleted":
                                task_filtered_vals[odoo_field] = task_stage_done.id if task_vals.get("IsCompleted", False) else task_stage_new.id
                            elif xteam_field == "IsLock" and odoo_field == "kanban_state":
                                task_filtered_vals[odoo_field] = "blocked" if task_vals.get("IsBlock", False) else "normal"
                            elif xteam_field == "ProjectId":
                                task_filtered_vals[odoo_field] = project_id
                            elif xteam_field == "IsArchived":
                                task_filtered_vals[odoo_field] = False if task_vals.get("IsArchived", False) else True
                            elif 'Unix' in xteam_field:
                                task_filtered_vals[odoo_field] = datetime.utcfromtimestamp(task_vals.get(xteam_field, False)).strftime("%Y-%m-%d %H:%M:%S") if task_vals.get(xteam_field, False) else False
                            elif xteam_field == 'IsPin':
                                task_filtered_vals[odoo_field] = '1' if task_vals.get("IsPin", False) else '0'
                            else:
                                task_filtered_vals[odoo_field] = task_vals.get(xteam_field, False)
                    if task_filtered_vals:
                        sub_tasks_vals_list = []
                        for sub_task_val in sub_task_vals:
                            sub_task_filtered_val = {}
                            print(sub_task_vals)
                            for odoo_field, xteam_field in mapped_xteam_task_fields.items():
                                if xteam_field in sub_task_val:
                                    if xteam_field == "OwnerId":
                                        xteam_user_id = sub_task_val["OwnerId"]
                                        odoo_user_id = mapped_users.get(xteam_user_id, OdooBotUser.id)
                                        sub_task_filtered_val[odoo_field] = odoo_user_id if odoo_user_id else 1
                                    elif xteam_field == "AssignedId" and sub_task_val.get("AssignedId", False):
                                        xteam_user_id = sub_task_val["AssignedId"]
                                        odoo_user_id = mapped_users.get(xteam_user_id, OdooBotUser.id)
                                        sub_task_filtered_val[odoo_field] = [odoo_user_id] if odoo_user_id else False
                                    elif xteam_field == "IsCompleted":
                                        sub_task_filtered_val[odoo_field] = task_stage_done.id if sub_task_val.get("IsCompleted", False) else task_stage_new.id
                                    elif xteam_field == "IsLock" and odoo_field == "kanban_state":
                                        sub_task_filtered_val[odoo_field] = "blocked" if sub_task_val.get("IsBlock", False) else "normal"
                                    elif xteam_field == "ProjectId":
                                        sub_task_filtered_val[odoo_field] = project_id
                                    elif xteam_field == "IsArchived":
                                        sub_task_filtered_val[odoo_field] = False if sub_task_val.get("IsArchived", False) else True
                                    elif 'Unix' in xteam_field:
                                        sub_task_filtered_val[odoo_field] = datetime.utcfromtimestamp(sub_task_val.get(xteam_field, False)).strftime("%Y-%m-%d %H:%M:%S") if sub_task_val.get(xteam_field, False) else False
                                    elif xteam_field == 'IsPin':
                                        sub_task_filtered_val[odoo_field] = '1' if sub_task_val.get("IsPin", False) else '0'
                                    else:
                                        sub_task_filtered_val[odoo_field] = sub_task_val[xteam_field]
                                sub_tasks_vals_list.append((0, 0, sub_task_filtered_val))
                            if not sub_task_filtered_val:
                                print('11111111')
                        if sub_tasks_vals_list:
                            print('1')
                        aa = [s[2]['active'] for s in sub_tasks_vals_list]
                        subtask_c = len(aa)
                        if sub_task_vals and not sub_tasks_vals_list:
                            print('ts k co ?')
                        if sub_tasks_vals_list:
                            print('1')
                        with open('/opt/python3.8-venv/count/tasks_count.txt', mode='a') as f:
                            f.writelines(f"{str(anz_project_id)}-{str(task_id)}-{str(1 if task_filtered_vals['active'] else 0)}-{str(len(sub_tasks_vals_list))}-{str(subtask_c)}\n")
                    print("done task: ", task_id)
                executor.submit(_sync_task, task_by_project_vals, odoo_project_id, xteam_project_id)
                # task_vals_list.append(filtered_vals)
    except Exception as e:
        print("Error when creating task here is the debugging: ", str(e))
        print("Xteam projects ids already created: ", created_xteam_projects_ids)
        print("Xteam tasks ids already created: ", created_xteam_tasks_ids)
        with open('/opt/python3.8-venv/count/project-error.txt', mode='a') as f:
            f.writelines(str(xteam_project_id) + str(e) + '\n')

executor.shutdown(wait=True)

print("--------done projects")