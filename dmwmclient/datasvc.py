import httpx
import pandas
from .util import format_dates


BLOCKARRIVE_BASISCODE = {
    -6: "no_source",
    -5: "no_link",
    -4: "auto_suspend",
    -3: "no_download_link",
    -2: "manual_suspend",
    -1: "block_open",
    0: "routed",
    1: "queue_full",
    2: "rerouting",
}


class DataSvc:
    """PhEDEx datasvc REST API

    Full documentation at https://cmsweb.cern.ch/phedex/datasvc/doc
    """

    defaults = {
        # PhEDEx datasvc base URL with trailing slash
        "datasvc_base": "https://cmsweb.cern.ch/phedex/datasvc/",
        # Options: prod, dev, debug
        "phedex_instance": "prod",
    }

    def __init__(self, client, datasvc_base=None, phedex_instance=None):
        if datasvc_base is None:
            datasvc_base = DataSvc.defaults["datasvc_base"]
        if phedex_instance is None:
            phedex_instance = DataSvc.defaults["phedex_instance"]
        self.client = client
        self.baseurl = httpx.URL(datasvc_base)
        self.jsonurl = self.baseurl.join("json/%s/" % phedex_instance)
        self.xmlurl = self.baseurl.join("xml/%s/" % phedex_instance)

    async def jsonmethod(self, method, **params):
        return await self.client.getjson(url=self.jsonurl.join(method), params=params)

    async def blockreplicas(self, **params):
        """Get block replicas as a pandas dataframe

        Parameters
        ----------
        block          block name, can be multiple (*)
        dataset        dataset name, can be multiple (*)
        node           node name, can be multiple (*)
        se             storage element name, can be multiple (*)
        update_since   unix timestamp, only return replicas whose record was
                        updated since this time
        create_since   unix timestamp, only return replicas whose record was
                        created since this time. When no "dataset", "block"
                        or "node" are given, create_since is default to 24 hours ago
        complete       y or n, whether or not to require complete or incomplete
                        blocks. Open blocks cannot be complete.  Default is to
                        return either.
        dist_complete  y or n, "distributed complete".  If y, then returns
                        only block replicas for which at least one node has
                        all files in the block.  If n, then returns block
                        replicas for which no node has all the files in the
                        block.  Open blocks cannot be dist_complete.  Default is
                        to return either kind of block replica.
        subscribed     y or n, filter for subscription. default is to return either.
        custodial      y or n. filter for custodial responsibility.  default is
                        to return either.
        group          group name.  default is to return replicas for any group.
        show_dataset   y or n, default n. If y, show dataset information with
                        the blocks; if n, only show blocks
        """
        resjson = await self.jsonmethod("blockreplicas", **params)
        df = pandas.io.json.json_normalize(
            resjson["phedex"]["block"],
            record_path="replica",
            record_prefix="replica.",
            meta=["bytes", "files", "name", "id", "is_open"],
        )
        format_dates(df, ["replica.time_create", "replica.time_update"])
        return df
    
    async def nodes(self, **params):
        
        """Returns a simple dump of phedex nodes.
        
        Parameters
        ----------
        node     PhEDex node names to filter on, can be multiple (*)
        noempty  filter out nodes which do not host any data
        """
        resjson = await self.jsonmethod("nodes", **params)
        df = pandas.io.json.json_normalize(
            resjson["phedex"],
            record_path="node",
            record_prefix="node.",
            
        )
        
        return df
    
    async def data(self, **params):
    
        """Shows data which is registered (injected) to phedex
        
        Parameters
        ----------
        
        dataset                  dataset name to output data for (wildcard support)
        block                    block name to output data for (wildcard support)
        file                     file name to output data for (wildcard support)
        level                    display level, 'file' or 'block'. when level=block
                                 no file details would be shown. Default is 'file'.
                                 when level = 'block', return data of which blocks were created since this time;
                                 when level = 'file', return data of which files were created since this time
        create_since             when no parameters are given, default create_since is set to one day ago
        """
        resjson = await self.jsonmethod("data", **params)
        out = []
        for _instance in resjson['phedex']['dbs']:
            for _dataset in _instance['dataset']:
                for _block in _dataset['block']:
                    for _file in _block['file']:
                    	out.append({
                    	'Dataset': _dataset['name'],
                    	'Is dataset open': _dataset['is_open'],
                    	'block Name': _block['name'],
                    	'Block size (GB)': _block['bytes']/1000000000.0,
                    	'Time block was created': _block['time_create'],
                    	'File name': _file['lfn'],
                    	'File checksum': _file['checksum'],
                    	'File size':  _file['size'],
                    	'Time file was created': _file['time_create']
                    })
        df = pandas.io.json.json_normalize(out)
        format_dates(df, ["Time file was created",'Time block was created'])
        return df
    
    #async def blockarrive(self,**params):
        """Returns estimated time of arrival for blocks currently subscribed for transfer. If it cannot be calculated, or the 
        block will never arrive, a reason for the missing estimate is provided.
        
        Parameters
        ----------
        id              block id
        block           block name, could be multiple, could have wildcard
        dataset         dataset name, could be multiple, could have wildcard
        to_node         destination node, could be multiple, could have wildcard
        priority        priority, could be multiple
        update_since    updated since this time
        basis           technique used for the ETA calculation, or reason it's missing - see below
        arrive_before   only show blocks that are expected to arrive before this time
        arrive_after    only show blocks that are expected to arrive after this time
        
        """
        
    async def errorlog(self, **params):
        
        """Return detailed transfer error information, including logs of the transfer and validation commands.
        Note that phedex only stores the last 100 errors per link, so more errors may have occurred then indicated by this API 
        call.
        
        Parameters
        ----------
        Required inputs: at least one of the followings: from, to, block, lfn
        optional inputs: (as filters) from, to, dataset, block, lfn

        from             name of the source node, could be multiple
        to               name of the destination node, could be multiple
        block            block name
        dataset          dataset name
        lfn              logical file name
        """
        
        resjson = await self.jsonmethod("errorlog", **params)
        out = []
        for _instance in data['phedex']['link']:
            for _block in _instance['block']:
                for _file in _block['file']:
                    for _transfer_error in _file['transfer_error']:
                        out.append({
                        'Link': _instance['from']+' to '+_instance['to'],
                        'LFN': _file['name'],
                        'file Checksum': _file['checksum'],
                        'file size (GB)': _file['size']/1000000000.0,
                        'Block name': _block['name'],
                        'Error log': str(_transfer_error['detail_log']['$t']),
                        'From PFN': _transfer_error['from_pfn'],
                        'To PFN': _transfer_error['to_pfn'],
                        'Time': _transfer_error['time_done']
                        })
        df = pandas.io.json.json_normalize(out)
        format_dates(df, ["Time"])
        return df
    
    async def blockarrive(self, **params):
        
        """Return estimated time of arrival for blocks currently subscribed for transfer. If the estimated time of arrival (ETA)
        cannot be calculated, or the block will never arrive, a reason for the missing estimate is provided.
        
        Parameters
        ----------
        id                    block id
        block                 block name, could be multiple, could have wildcard
        dataset               dataset name, could be multiple, could have wildcard
        to_node               destination node, could be multiple, could have wildcard
        priority              priority, could be multiple
        update_since          updated since this time
        basis                 technique used for the ETA calculation, or reason it's missing.
        arrive_before         only show blocks that are expected to arrive before this time.
        arrive_after          only show blocks that are expected to arrive after this time.

        """
        
        resjson = await self.jsonmethod("blockarrive", **params)
        out = []
        for _block in resjson['phedex']['block']:
            for _destination in _block['destination']:
                out.append({
                'Block Name': _block['name'],
                'Destination':_destination['name'],
                'Time Arrive': _destination['time_arrive'],
                'Time update':_destination['time_update'],
                'Number of files':_destination['files'],
                'Block size (GB)':_destination['bytes']/1000000000.0,
                'Basis code':_destination['basis']
                    })
        df = pandas.io.json.json_normalize(out)
        format_dates(df, ["Time Arrive",'Time update'])   
        return df
    
    async def filereplicas(self,**params)
    
        """Serves the file replicas known to phedex.
        
        Parameters
        ----------
        block          block name, with '*' wildcards, can be multiple (*).  required when no lfn is specified. Block names must 
                       follow the syntax /X/Y/Z#, i.e. have three /'s and a '#'. Anything else is rejected.
        dataset        dataset name. Syntax: /X/Y/Z, all three /'s obligatory. Wildcads are allowed.
        node           node name, can be multiple (*)
        se             storage element name, can be multiple (*)
        update_since   unix timestamp, only return replicas updated since this
                time
        create_since   unix timestamp, only return replicas created since this
                       time
        complete       y or n. if y, return only file replicas from complete block
                       replicas.  if n only return file replicas from incomplete block
                       replicas.  default is to return either.
        dist_complete  y or n.  if y, return only file replicas from blocks
                       where all file replicas are available at some node. if
                       n, return only file replicas from blocks which have
                       file replicas not available at any node.  default is
                       to return either.
        subscribed     y or n, filter for subscription. default is to return either.
        custodial      y or n. filter for custodial responsibility.  default is
                       to return either.
        group          group name.  default is to return replicas for any group.
        lfn            logical file name
        """
        resjson = await self.jsonmethod("filereplicas", **params)
        out = []
        for _block in resjson['phedex']['block']:
            for _file in _block['file']:
                for _replica in _file['replica']:
                    out.append({
                    'Block_name':_block['name'],
                    'Files in block':_block['files'],
                    'Block size (GB)':_block['bytes']/1000000000.0,
                    'File name':_file['name'],
                    'File checksum':_file['checksum'],
                    'File created on':_file['time_create'],
                    'File replica at':_replica['node'],
                    'File subcribed?':_replica['subscribed'],
                    'Custodial?':_replica['custodial'],
                    'Group':_replica['group'],
                    'File in node since':_replica['time_create']
                    })
        df=json_normalize(out)
        format_dates(df, ["File created on",'File in node since'])        