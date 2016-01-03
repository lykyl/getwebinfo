#!/usr/bin/env python
#coding:UTF-8
#ver 1.0

import os,datetime,re,hashlib,urlparse,sqlite3,pickle,urllib,urllib2,sys,Queue,string,threading,logging,time
from xml.etree import ElementTree
from EnigmaClass import ItemClass,SiteClass,getRemoteFile
import EnigmaFunc

class getInfo(threading.Thread):
    def __init__(self,threadName,SiteInfo):
        threading.Thread.__init__(self, name=threadName)
        self.Site=SiteInfo
        self.downLoadQueue=Queue.Queue()
        self.ContStore={}    #抓取内容缓存
        self.AppPath=os.path.split(os.path.realpath(__file__))[0]+os.sep     #程序所在目录
        self.log=self.initLog(threadName)
        self.getFile=getRemoteFile(threadName+"_getfile",self.downLoadQueue,self.log)
        self.getFile.start()
        
    def initLog(self,name):
        log=logging.getLogger(name)
        log.level=logging.DEBUG
        if len(log.handlers)>0:
            th=log.handlers[0]
            if th.name!=(name+".log"):
                log.removeHandler(th)
            else:
                return log
        logFormat=logging.Formatter('%(filename)s (Thread:%(threadName)s) [%(asctime)s] \n %(levelname)s: %(message)s')
        fn=logging.FileHandler(self.AppPath+"logs"+os.sep+name+".log")
        fn.setFormatter(logFormat)
        fn.name=name+".log"
        log.addHandler(fn)
        return log
        
        
    def run(self):
        self.log.info(self.Site.Name+u" 开始处理")     
        #time.sleep(15)
        #logging.info(self.Site.Name+" 结束处理")     
        #return True    
        start = time.clock()
        strWebContent=EnigmaFunc.GetWeb(self.Site.Url,self.Site.Code)                    
        if len(strWebContent)<10:
            self.log.info(u"%s 网站内容无效,跳过此站" % (self.Site.Name))
            return False
        #获取字段内容
        strStoreId=self.UpdateContStore(strWebContent)
        #整理URL路径并保存，方便后面程序使用
        UrlInfo=urlparse.urlparse(self.Site.Url)
        self.ContStore["siteurl"]=self.Site.Url
        self.ContStore["sitebaseurl"]=UrlInfo.scheme+"://"+UrlInfo.netloc
        if UrlInfo.path.endswith("/"):
            self.ContStore["sitecurrenturl"]=self.ContStore["sitebaseurl"]+UrlInfo.path[0:len(UrlInfo.path)-1]
        else:            
            self.ContStore["sitecurrenturl"]=self.ContStore["sitebaseurl"]+UrlInfo.path
        self.GetItems(self.Site.Items,strStoreId,self.Site)
        self.ContStore.clear() 
        self.downLoadQueue.put((self.Site.ShortName,"__END__"))
        self.getFile.join()
        end = time.clock()
        runtime=end-start
        self.log.info(u"%s 运行完毕，所用时间%fs" %(self.Site.Name,runtime))
        return True                          

    def GetItems(self,xmlItems,strKey,Site):
        "抓取网站字段内容"
        
        result={}       #POST字段暂存字典
        if xmlItems==None or not self.ContStore.has_key(strKey):
            self.log.warning("%s xmlitems is empty" %(strKey))
            return result
        for node in xmlItems.getchildren():
            aFilter=[]      #过滤标签
            aCont=[]        #符合条件的内容
            strName=EnigmaFunc.ForceCode(node.tag)      #抓取节点名称
            strContent=u""      #抓取内容
            strFCont=u""        #内容节点条件内容前缀
            strTCont=u""        #内容节点条件内容后缀
            strLink=""          #抓取链接
            bAllowRep=node.attrib.has_key("allowrep")       #是否循环多次抓取
            bInLink=node.attrib.has_key("inlink")       #抓取对象为链接指向网页中的内容
            bIsRow=node.attrib.has_key("isrow")     #是否为一条完整的数据行内容（通常需要保存到目标CMS数据库中）
            strField=EnigmaFunc.GetXmlNodePropVal("field",node)      #关键内容对应的POST字段名（通常需要保存到目标CMS数据库中）
            strKeyField=EnigmaFunc.GetXmlNodePropVal("keyfield",node)      #关键内容对应的数据库字段名（需要存到本地抓取库中）
            bSplitMerge=False    #多页内容是否合并
            #print strName.encode(EnigmaFunc.Coding)+"处理中..."
            #EnigmaFunc.SimpleLog("info",strName.encode(EnigmaFunc.Coding)+"处理中...")
            aFilter=EnigmaFunc.GetXmlNodeVal("./filter",node).strip().lower().split("|")
            strContent=EnigmaFunc.GetXmlNodeVal("./content",node)
            strLocal=EnigmaFunc.GetXmlNodeVal("./local",node)
            if len(strLocal)>0:
                strLocal="files/"+strLocal
                strFullPath=self.AppPath+strLocal
                if not os.path.exists(strFullPath):
                    try:
                        os.makedirs(strFullPath)
                    except OSError,e:
                        strLog=strFullPath+" 目录创建失败,跳过此项。原因:"+str(e)
                        self.log.warning(strLog)
                        continue
            rContent=self.CreateFilter(strContent)
            if rContent is None:
                aCont.append(strContent)
            if bInLink :
                #self.ContStore[strKey+"!"]存放链接指向页面的内容
                if self.ContStore.has_key(strKey+"!"):
                    strContent=self.ContStore[strKey+"!"]
                else:
                    strLink=self.GetFullLink(self.ContStore[strKey])
                    if Site.State=="test":
                        self.log.info("进入链接："+strLink)
                    strContent=EnigmaFunc.GetWeb(strLink,Site.Code)
                    if len(strContent)<5:
                        self.log.info("%s链接内容 %s 无效,跳过此项" % (strLink,strContent))
                        continue 
                    self.ContStore[strKey+"!"]=strContent
            else:
                strContent=self.ContStore[strKey]
            if rContent is not None :
                aCont=rContent.findall(strContent)            
            if aCont is None :            
                self.log.info("%s 具体内容获取失败,跳过此项" %(strName))
                continue 
            elif len(aCont)<1:
                self.log.info("%s 具体内容获取失败,跳过此项" %(strName))
                continue 
            strSplitLink=""
            strSplit=EnigmaFunc.GetXmlNodeVal("./split",node)
            if self.ContStore.has_key("splitmax"):
                nSplitMax=self.ContStore["splitmax"]
            else:
                nSplitMax=999999
            it=node.find("./split")
            if it is not None:
                if nSplitMax>=999999:
                    st=EnigmaFunc.GetXmlNodePropVal("max",it)
                    if len(st)>0:
                        nSplitMax=string.atoi(st)
                    else:
                        nSplitMax=nSplitMax-1
                    self.ContStore["splitmax"]=nSplitMax
                bSplitMerge=it.attrib.has_key("merge")
                rSplit=self.CreateFilter(strSplit)
                if rSplit is not None:
                    match=rSplit.search(strContent)   
                    if match is not None:
                       strSplitLink=match.group(1)         
            for Con in aCont:
                Con=Con.strip()
                if len(Con)<1:
                    self.log.info("%s 抓取内容为空，跳过。" %(strName))
                strStoreId=self.UpdateContStore(Con)
                if len(strField)>0 or len(strLocal)>0 or len(strKeyField)>0:
                    strValue=self.FixLink(EnigmaFunc.FilterHtml(Con,aFilter),False)
                if len(strKeyField)>0:
                    if Site.CheckDuplicate:
                        strFData=EnigmaFunc.CheckWebContent(strValue)
                        strSql="select count(*) from t_info where f_"+strKeyField+"='"+strFData+"'"
                        with sqlite3.connect(Site.DBFile) as conn:
                            rs=conn.cursor()
                            rs.execute(strSql)                
                            rowCount=rs.fetchone()
                            if rowCount[0]>0:
                                result["__skip"]=1
                                self.log.info("已有采集记录，跳过"+Con)
                                if not bAllowRep :
                                    break
                                else:
                                    continue
                    result["_db_"+strKeyField]=strFData
                #print stName.encode(EnigmaFunc.Coding)+"子集获取："
                for nodeitems in node.findall("items"):
                    result.update(self.GetItems(nodeitems,strStoreId,Site).copy())
                self.ContStore[strStoreId]=None
                #当抓取项目是测试状态时不做图片本地化处理
                if len(strLocal)>0 and Site.State!="test":
                    strValue=self.GetURLFile(strValue,strLocal)
                if len(strField)>0:
                    result[strField]=strValue
                if bIsRow:
                    if result.has_key("__skip") and result["__skip"]==1:
                        pass
                    else:
                        keyResult={}    #本地抓取库字段暂存字典
                        for i in result.keys():
                            if len(i)>4 and i[0:4]=="_db_":
                                keyResult[i[4:]]=result[i]
                        strLog="keyResult"
                        for i in keyResult.keys():
                            strLog+=" %s : %s" % (i,keyResult[i])
                            del result["_db_"+i]
                        #如果是测试抓取，则不做POST和入库操作
                        if Site.State!="test":
                            keyResult["poststate"]=self.PostData(result,Site)
                            self.Put2Db(keyResult,Site)
                        else:
                            #在测试模式输出抓取结果集
                            self.log.info(strLog)
                            strLog= "Result"
                            for i in result.keys():
                                strLog+= " %s : %s" % (i,result[i])
                            self.log.info(strLog)
                            keyResult["poststate"]=True
                        #EnigmaFunc.SimpleLog("!info!",u"完成一组数据采集")
                if not bAllowRep :
                    break
            if len(strSplitLink)>0:
                nSplitMax=nSplitMax-1
                self.ContStore["splitmax"]=nSplitMax
                if nSplitMax>0:
                    self.log.info("splitLink:"+strSplitLink)
                    if bInLink:
                        strSplitCont=strSplitLink
                    else:
                        strSplitCont=EnigmaFunc.GetWeb(self.GetFullLink(strSplitLink),Site.Code)
                    if len(strSplitCont)>5:
                        strStoreId=self.UpdateContStore(strSplitCont)
                        t=self.GetItems(xmlItems,strStoreId,Site).copy()
                        if bSplitMerge:
                            result[strField]=result[strField]+t[strField]
                        self.ContStore[strStoreId]=None
            
        return result
    
    def CreateFilter(self,strValue):
        "生成过滤内容正规式"
        tf=strValue.split("{$")
        tt=strValue.split("$}")
        if len(tf)==2 and len(tt)==2:
            strFCont=re.escape(EnigmaFunc.ForceCode(tf[0]))                 
            strTCont=re.escape(EnigmaFunc.ForceCode(tt[1]))                 
            strRe=tf[1][:len(tf[1])-len(tt[1])-2]
            r=re.compile(strFCont+"("+strRe+"?)"+strTCont,re.S)
        else:
            #如果content节点中不包含{$*$}则取值固定为节点中的内容。
            r=None
        return r
    
    def GetURLFile(self,strContent,strLocal):
        "获取远程文件"

        re_data = re.compile(r'(?P<f>img.*?src\s*=[\'\"])(?P<content>.[^\'\"]*)', re.I|re.S)
        strFullPath=self.AppPath+strLocal+os.path.sep
        for match in re_data.finditer(strContent):
            fileInfo=(match.group(2),strFullPath)
            self.downLoadQueue.put(fileInfo)
        strContent=re_data.sub(r"\1"+strLocal.replace("\\","/")+r"/\2",re_data.sub(self.remote2local,strContent))
        return strContent
    
    def remote2local(self,match):
        UrlInfo=urlparse.urlparse(match.group(2))
        fileName=match.group(1)+UrlInfo.path.split("/")[-1].strip()
        return fileName
    
    def PostData(self,aData,Site):   
        "将抓取数据发送到目标服务" 
        bReturn=True
        aData.update(Site.PostArg.copy())
        #print aData
        PostArg=urllib.urlencode(aData)
        #EnigmaFunc.SimpleLog("Info",PostArg)
        try: 
            PostMsg=urllib2.urlopen(Site.PostUrl,PostArg).read()
            self.log.info("postResult:%s" % (PostMsg))
        except Exception,e:
            bReturn=False
            self.log.warning("PostError:%s" % (e.__class__.__name__))    
        return bReturn
    
    def Put2Db(self,aData,Site):
        "已抓取数据入库"
        
        strSql=u"insert into t_info (f_url,f_site,f_title,f_state) values('"+aData["url"]+"','"+Site.Name+"'"
        if aData.has_key("title"):
            strSql=strSql+",'"+aData["title"]+"',"     
        else:
            strSql=strSql+",''"   
        if aData["poststate"]:
            strSql=strSql+"0)"
        else:
            strSql=strSql+"1)"
        self.log.info("sql %s" % (strSql))
        with sqlite3.connect(Site.DBFile) as conn:
            rs=conn.cursor()
            rs.execute(strSql)                
    
    def GetFullLink(self,strLink):
        "生成完整URL"
        
        UrlInfo=urlparse.urlparse(strLink)     
        if len(UrlInfo.netloc)<1:
            if strLink.startswith("./"):
                strLink=self.ContStore["sitecurrenturl"]+"/"+strLink[2:len(strLink)-3]
            else:
                if strLink.startswith("/"):
                    strLink=self.ContStore["sitebaseurl"]+strLink
                else:
                    if strLink.startswith("../"):
                        if self.ContStore["sitecurrenturl"]==self.ContStore["sitebaseurl"]:
                            strLink=self.ContStore["sitebaseurl"]+strLink
                        else:
                            strLink=self.ContStore["sitecurrenturl"][:self.ContStore["sitecurrenturl"].rfind("/")+1]+strLink 
                    else:
                        strLink=self.ContStore["sitecurrenturl"]+"/"+strLink
        return strLink
    
    def FixLink(self,strContent,bDirectLink):
        if bDirectLink:
            if strContent[:5]!="http:" and strContent[:6]!="https:":
                if strContent[0]=="/":
                    strContent=self.ContStore["sitebaseurl"]+strContent
                else:
                    strContent=self.ContStore["sitecurrenturl"]+strContent            
        else:
            re_data = re.compile('(?P<f>(href|src)\s*=[\'\"])(?P<content>/[^\'\"]*)(?P<t>[\'\"])', re.I|re.S)
            strContent=re_data.sub(r"\1"+self.ContStore["sitebaseurl"]+r"\2\3",strContent)
            re_data = re.compile('(?P<f>(href|src)\s*=[\'\"])(?P<content>\.[^\'\"]*)(?P<t>[\'\"])', re.I|re.S)
            strContent=re_data.sub(r"\1"+self.ContStore["sitecurrenturl"]+r"\2\3",strContent)
        return strContent      
    
    def UpdateContStore(self,strInput):
        "创建新的抓取内容缓存，返回唯一KEY,KEY对应的VALUE为入参。"
        
        MD5=hashlib.md5()
        MD5.update(strInput.encode(EnigmaFunc.Coding))
        result=MD5.hexdigest()
        self.ContStore[result]=strInput
    
        return result