Route53 SPF Flattener
=======

* `r53spflat` is an extension to [sender-policy-flattener](https://github.com/cetanu/sender_policy_flattener) which is a different project maintaind by ***centanu***.
* `r53spflat` can update the SPF TXT records in [Amazon Route53](https://aws.amazon.com/route53)
* `r53spflat` was adapted from [`cfspflat`](https://github.com/Glocktober/cfspflat) - which provides the same capability for Cloudflare DNS

### SPF Flattening
[Sender Policy Framework](http://www.open-spf.org/Introduction/) [(SPF) has certain restricitions](https://tools.ietf.org/html/rfc7208#section-4.6.4) on the number of DNS lookups (10) to validate a sender is authorized by SPF.
* Organizations utilizing vendors and SaaS products that send email on their behalf. They do this by adding an `include` for an SPF record the vendor provides - and manages.  
* The vendor managed SPF record contains the `ip4` and `ip6` records for that vendors email infrastrucure and often contains additional `include` statements.
* As each vendor SPF record is included to your SPF it requires more DNS lookups.  This can exceed the SPF protocol limit of 10 lookups. When this happens, your email can be rejected by recipients because the authorized sender's IP was never reached.
* SPF Flattening is the process of resolving the authorized senders SPF `include` records into `ip4` and `ip6` records to reduce the number of DNS lookups.
* Converting the `include` records to `ip4` and `ip6` statements can be a problem if the vendor modifies their SPF record. How do you keep them in sync?
    * [sender-policy-flattener]() detects these changes and reports them by email.
    * `r53spflat` uses `sender-policy-flattener`, but includes an `--update` capability.


## `r53spflat` - Route53 Sender Policy Flattener

Quick overview:
```bash
% r53spflat -h
usage: r53spflat [-h] [-c CONFIG] [-o OUTPUT] [--update-records] [--force-update]
          [--no-email]

A script that crawls and compacts SPF records into IP networks. This helps to
avoid exceeding the DNS lookup limit of the Sender Policy Framework (SPF)
https://tools.ietf.org/html/rfc7208#section-4.6.4

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Name/path of JSON configuration file (default:
                        spfs.json)
  -o OUTPUT, --output OUTPUT
                        Name/path of output file (default spf_sums.json)
  --update-records      Update SPF records in Route53
  --force-update        Force an update of SPF records in Route53
  --no-email            don't send the email
```
* The `sender-policy-flattener` python module is installed as part of `r53spflat`
* The existing core of `spflat` is kept mostly intact, so the basic features are maintained by `r53spflat`.  
* The changes to accomodate `r53spflat` were in the parameter handling and adding the Route53 updates to the processing look.
* The `boto3` library, with some abstraction classes, is used to make the zone updates in Route53.
* `r53spflat` eliminates many of the command arguments of spflat in favor of using the json config file.
* Rotue53 TXT records are automatically generated and updated when the configuration changes.
* With `r53spflat` you can completely automate your SPF flattening using cfspflat with the `--update` switch in a cron job, even silently with the `--no-email` switch

## Installing and Configuring `r53spflat`

### 1. pip install the r53spflat module
```bash
% pip install r53spflat
```
* But it's advisable to do this in its own venv:
```bash
% python3 -m venv spfenv
% source spfenv/bin/activate
% pip install r53spflat
```
* pip will install the prerequisites, including the `sender-policy-flattner` (spflat), `dnspython`, `netaddr`, and `boto3` python modules.
* The executable is installed in bin of the venv as `r53spflat`
### 2. Create an anchor SPF record for the zone apex in Route53

Create the TXT SPF record on zone apex used (e.g. example.com), At the end of this anchor record include the first SPF record that slpat will write - spf0.example.com
 * we also include our own `ip4` and `ip6` entries in this anchor record. 
```
example.com TXT "v=spf1 mx include:spf0.example.com -all"
```
* This anchor record is never changed by `r53spflat`. It's purpose is to link to the first SPF record in the chain that `r53spflat` manages.

### 2. Edit the r53spflat configuration file
Create a spfs.json file.  Add all the entries required:
* `r53spflat` uses the same configuration and sums file formats as the original `spflat`.
* If you already use spflat you can use those files as is with r53spflat.
* There is one extension - the "update_subject" entry containing the subject of the email sent when r53spflat has updated your SPF records.  This message will contain the same detail spflat provides.
* `spfs.json` is the default name of the config file, but it can be specified with the `--config` switch.
* Here is an example config file:
#### Example spfs.json configuration file:
```json
{
    "sending domains": {
        "example.edu": {
              "amazonses.com": "txt",
              "goodwebsolutions.net": "txt",
              .... more sender spf's here ....
              "delivery.xyz.com": "txt",
              "spf.protection.outlook.com": "txt"
        }
    },
    "resolvers": [
            "1.1.1.1", "8.8.8.8"
    ],
    "email": {
        "to": "dnsadmins@example.com",
        "from": "spf_monitor@example.com",
        "subject": "[WARNING] SPF Records for {zone} have changed and should be updated.",
        "update_subject" : "[NOTICE] SPF Records for {zone} have been updated.",
        "server": "smtp.example.com"
    },
    "output": "monitor_sums.json"
}
```
#### Config file details
* The `sending domains` section is **required** and contains sending domain entries: this is your sender domain (e.g. example.com for j.smith@example.com, noreply.example.com for deals@noreply.example.com )  There can be multiple sending domains in the config file.
* Each sending domain contains dns spf records for the dns `include` records of your approved senders.These dns names are resolved and flattened:
  * These entries are in the key-value pairs of <fqdn> : <record type>.
  * Record type can be "txt" (other SPF records),  "A" and "AAAA" records (for specific hosts).
* The `resolvers` section is **optional** (using the system default DNS resolvers if none are supplied)
* The `email` stanza is **required** and is global (i.e. for all `sending domains`).  This section includes:
  * `subject` **(optional)** is the email subject if a change was detected but no updates were made. The default message is the one shown in the example.
  * `update_subject` **(optional)** is the email subject if a change was detected and the dns records were updated. The default message is shown in the example.
    * `to` - is **required** - this is the destination for emails sent by `r53spflat` 
    * `from` - is **required** - the source email of the messages `r53spflat` sends
    * `server` - is **required** - your mail relay.
* `output` is the file that maintains the existing state and checksum of sender records. If this is not specified `spfs_sum.json` is used.
#### Output file details
* The `output` file is a JSON file only updated if it is new (empty) or the records have been updated. 
* Likewise the default output file is `spf_sums.json` but can be changed in the config file or by the `--output` switch.
* This contains the list of flattened spf records and a checksum used to assess changes in senders records. 
* Because you recieve emails of detected changes or updates, there is little reason to care about the output file.
### 3. Create a credentials file for AWS
* The AWS user or role used for `r53spflat` must have these permissions to make updates:
    * `ListHostedZones` to Route53
    * `ChangeResourceRecordSets` to the zones that will be updated 
* If `r53spflat` run on an AWS EC2 instance, an IAM role with the required privileges can be attached to the instance.
* If `r53spflat` runs on prem, API keys are required to make the AWS Route53 updates and placed in a configuation file.
    * Configuring this beyond our scope: refere to [AWS cli](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
    * Route53 is a global service, so any region can be specified.
    * These credentials are typically in `~/.aws/credentials` and `~/.aws/config`
* It's also possible to pass the credentials as environment variables.

### 4. Run `r53spflat` to build the sums file and SPF entries
* Run r53spflat twice:
```bash
% r53spflat --no-email
% r53spflat --force 
```
* The first time constructs the base records and the second time forces the dns updates.
* With force update the DNS records are created even if a change hasn't been detected.
* A list of the records will be sent to your email.

### 5. Automate `r53spflat` to the level you are comfortable with
* You are up and running:
  * You can run `r53spflat` in advisory mode (like `spflat`) sending you emails notifying of changes
  * Or you can run it with the `--update-records` switch and update your records automatically whenever they change (still giving you notifications of the changes made.)

Example email format
--------------------
* Example from `sender-policy-flattener` README
* This would be in 

<img src='https://raw.githubusercontent.com/cetanu/sender_policy_flattener/master/example/email_example.png' alt='example screenshot'></img>
