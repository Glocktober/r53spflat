import boto3


def aws_ok(resp):
    """ Return true if response status is ok """

    if resp['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    return False


class R53zone:
    """ Rt53 dns zone """

    def __init__(self, domain):

        self.r53 = boto3.client('route53')

        zone_info = self.get_zoneid(domain)
        
        self.zoneid = zone_info['id']
        self.zonename = zone_info['name']

    
    def get_all_r53_zones(self):
        """ Get all Rt53 zones in this account """

        resp = self.r53.list_hosted_zones()
        
        if aws_ok(resp) is False:
            raise Exception('Failed to get account RT53 Zone info')
        
        return {z['Name']:z['Id'] for z in resp['HostedZones']}


    def get_zoneid(self, fqdn):
        """ Interate through fqdn until we find a zonename match """

        r53zones = self.get_all_r53_zones()
        
        fparts = fqdn.split('.')
        while(fparts):
            for z in r53zones:
                if '.'.join(fparts) ==  z[:-1]:
                    return {'name':z, 'id': r53zones[z]}
            
            fparts = fparts[1:]

        raise Exception('No Matching Zones in Route53')
    

    def change_record(self, action, recordset):
        """ Change a resource record: CREATE/UPSERT/DELETE """

        r = self.r53.change_resource_record_sets(
            HostedZoneId = self.zoneid,
            ChangeBatch = {
                'Changes':[
                    {
                        'Action': action,
                        'ResourceRecordSet': recordset
                    }
                ]
            }
        )
        
        return aws_ok(r)


    def get_recordset(self, fqdn, type,):
        """ Return Resource Record Set """
        
        resp = self.r53.list_resource_record_sets(
            HostedZoneId = self.zoneid,
            StartRecordName = fqdn.lower(),
            StartRecordType = type,
            MaxItems = '1'
        )

        if aws_ok(resp):
            # Is this the record we asked for?
            if len(resp['ResourceRecordSets'])>0:
                recordset = resp['ResourceRecordSets'][0]

                if  recordset['Name'].lower() == fqdn.lower() and \
                    recordset['Type'] == type:
                    return recordset
            
        return None


class   Rt53rec:
    """ Rt53 Resource Record """

    def __init__(self, domain, type='A', ttl=300):
        """ Manage Rt53 Resource Record """

        self.type = type.upper()
        self.ttl = ttl
        self.zone = R53zone(domain)
        self.zonename = self.zone.zonename


    def canonical(self, name):
        """ For fqdn with partials"""

        if name.endswith(self.zonename):
            return name
        elif name.endswith(self.zonename[:-1]):
            return name + '.'
        else:
            return f'{name}.{self.zonename}'


    def add(self, name, contents):
        """ Add a Resource Record """

        fqdn = self.canonical(name)

        if type(contents) is not list:
            contents = [contents]
        
        resourcerecords = [{'Value': val} for val in contents]

        return self.zone.change_record('CREATE', {
                'Name': fqdn,
                'Type': self.type,
                'TTL' : self.ttl,
                'ResourceRecords' : resourcerecords
            }
        )


    def update(self, name, contents, addok=False):
        """ Update a Resource Record """

        fqdn = self.canonical(name)
        
        if type(contents) is not list:
            contents = [contents]
        
        resourcerecords = [{'Value': val} for val in contents]
        
        resourceset = self.zone.get_recordset(fqdn, self.type)
        
        if resourceset:
            resourceset['ResourceRecords'] = resourcerecords
        elif addok == False:
            return False
        else:
            resourceset ={
                'Name': fqdn,
                'Type': self.type,
                'TTL': self.ttl,
                'ResourceRecords': resourcerecords,
            }
        return self.zone.change_record('UPSERT', resourceset)
        

    def get(self, name):
        """ 
        Retrieve contents of resource record 
        
        """

        fqdn = self.canonical(name)
        
        resourceset = self.zone.get_recordset(fqdn, self.type)
        
        if resourceset:
            resourcerecords = resourceset['ResourceRecords']
            return [val['Value'] for val in resourcerecords]
        else:
            return None


    def rem(self,name):
        """ remove zone record """

        fqdn = self.canonical(name)
        
        resourceset = self.zone.get_recordset(fqdn, self.type)
        
        if resourceset:
            return self.zone.change_record('DELETE',resourceset)
        return False       

    
class TXTrec(Rt53rec):
    """ Rt53 TXT record """

    def __init__(self,domain):

        super().__init__(domain,'TXT')


    def _quote_txt(self, contents):
        """ TXT records must be quoted and in 255 byte strings """

        if type(contents) is not list:
            contents = [contents]

        results = []
        for content in contents:
            quoted = f'"{content}"'
            if len(quoted) > 255:
                # break into separate quoted strings on 
                # nearest space.
                i = quoted[:254].rfind(' ')
                quoted = quoted[:i] +'" "' + quoted[i:]
            results.append(quoted)

        return results


    def _unquote_txt(self, contents):
        """ unquote TXT record """

        results = []
        for content in contents:
            unquoted=content[1:-1]
            if len(content)>255:
                i = unquoted[:254].rfind('" "')
                print('uu',i)
                unquoted = unquoted[:i] + unquoted[i+3:]
            results.append(unquoted)

        return results
        

    def add(self, name, contents):

        return super().add(name, self._quote_txt(contents))


    def update(self, name, contents, addok=False):

        return super().update(name, self._quote_txt(contents), addok)


    def get(self, name):
        content = super().get(name)
        
        if content:
            return self._unquote_txt(content)

        return content


class Arec(Rt53rec):
    """ Rt53 A record """

    def __init__(self,domain):

        super().__init__(domain,'A')
    

class AAAArec(Rt53rec):
    """ Rt53 AAAA record """

    def __init__(self,domain):

        super().__init__(domain,'AAAA')
    

class CNAMErec(Rt53rec):
    """ Rt53 CNAME record """

    def __init__(self,domain):

        super().__init__(domain,'CNAME')
     
     
class MXrec(Rt53rec):
    """ Rt53 CNAME record """

    def __init__(self,domain):

        super().__init__(domain,'MX')
     