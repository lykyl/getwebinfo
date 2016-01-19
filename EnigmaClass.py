#!/usr/bin/env python
#coding:UTF-8

import os,datetime,urlparse,threading,Queue,urllib2,logging,EnigmaFunc,sqlite3
from xml.etree import ElementTree

class getRemoteFile(threading.Thread):
    def __init__(self,threadName,getQueue,log):
        threading.Thread.__init__(self, name=threadName)
        self.getQueue=getQueue
        self.AppPath=os.path.split(os.path.realpath(__file__))[0]+os.sep     #程序所在目录
        self.log=log
    
    def run(self):
        while (True):
            try:
                fileUrl=self.getQueue.get(1)
                if fileUrl[1]=="__END__":
                    self.log.info("%s finished." %(fileUrl[0]))
                    break
                else:
                    self.log.info("getting %s" % (fileUrl[0]))
                    self.getFile(fileUrl[0], fileUrl[1])
            except:
                self.log.info("%s finished." %(self.getName()))
                break
     
        
    def getFile(self,strUrl,LocalPath,nTryTime=3):
        "获取指定URL文件"
        
        while (nTryTime>0):
            try:
                UrlInfo=urlparse.urlparse(strUrl)
                fileName=LocalPath+UrlInfo.path.split("/")[-1].strip()
                req=urllib2.Request(strUrl, headers={'User-Agent' : "Mozilla/5.0 (Windows; U; Windows NT 5.1) Gecko/20070803 Firefox/1.5.0.12"})
                data=urllib2.urlopen(req)
                with open(fileName,"wb") as file:
                    file.write(data.read())
                print fileName
                nTryTime=-10
            except Exception,e:
                print e
                nTryTime-=1
                
class ItemClass(object):
    "抓取项目类"
    Name=u""
    Base="url"
    Filter=[]
    Content=u""
    FCont=u""
    TCont=u""

    def __init__(self,strName=u"",strBase="",strFilter="",strContent=u""):
        self.SetName(strName)
        self.SetBase(strBase)
        self.SetFilter(strFilter)
        self.SetContent(strContent)        
            
    def SetName(self,strName=u""):
        self.Name=strName.strip().lower()
    
    def SetBase(self,strBase=""):
        self.Base=strBase.strip().lower()
        if len(self.Base)<1:
            self.Base="url"
            
    def SetFilter(self,strFilter=""):
        self.Filter=strFilter.strip().lower().split("|")
    
    def SetContent(self,strContent=u""):
        self.Content=strContent
        t=strContent.split("{$*$}")
        if len(t)==2:
            self.FCont=t[0]
            self.TCont=t[1]


class SiteClass(object):
    "抓取站点信息类"
    Name=u""
    ShortName=u""
    Url=""    
    Code="utf-8"
    Items=None
    PostUrl=""
    DBFile=""
    State="run"
    PostArg={}
    CheckDuplicate=False
    ConfigFile=""
    Interval=datetime.timedelta(seconds=86400)
    LastRunTime=datetime.datetime.now()
    NextRunTime=datetime.datetime.now()
    
    SiteBaseUrl=""
    SiteCurrentUrl=""

    def __init__(self,strName=u"",strShortName=u"",strUrl="",strCode="utf-8",strState="run",strPostUrl="",strDatabase="",bCheckDuplicate=False,nInterval=86400):
        self.SetName(strName)
        self.SetShortName(strShortName)        
        self.SetUrl(strUrl)
        self.SetCode(strCode)
        self.SetState(strState)
        self.SetPostUrl(strPostUrl)
        self.SetDBFile(strDatabase)
        self.SetInterval(nInterval)
        self.CheckDuplicate=bCheckDuplicate
    
    def SetName(self,strName=u""):
        self.Name=strName.strip().lower()

    def SetShortName(self,strShortName=u""):
        self.ShortName=strShortName.strip().lower()  
              
    def SetState(self,strState="run"):
        self.State=strState.strip().lower()  
        
    def SetConfigFile(self,strFile):
        self.ConfigFile=strFile.strip()  

    def SetUrl(self,strUrl=""):
        self.Url=strUrl.strip()
        #整理URL路径并保存，方便后面程序使用
        UrlInfo=urlparse.urlparse(self.Url)
        self.SiteBaseUrl=UrlInfo.scheme+"://"+UrlInfo.netloc
        if UrlInfo.path.endswith("/"):
            self.SiteCurrentUrl=self.SiteBaseUrl+UrlInfo.path[0:len(UrlInfo.path)-1]
        else:            
            self.SiteCurrentUrl=self.SiteBaseUrl+UrlInfo.path
    
    def SetCode(self,strCode="utf-8"):
        self.Code=strCode.strip().lower()
        if len(self.Code)<1:
            self.Base="utf-8"
            
    def SetPostUrl(self,strPostUrl=""):
        self.PostUrl=strPostUrl.strip()
        
    def SetDBFile(self,strDB=""):
        self.DBFile=strDB.strip()
        
    def SetPostArg(self,aArg):
        self.PostArg=aArg
        
    def SetInterval(self,nInterval=86400):
        self.Interval=datetime.timedelta(seconds=nInterval)   
        self.NextRunTime=self.LastRunTime+self.Interval    
        
    def SetLastRunTime(self,dtTime):
        self.LastRunTime=dtTime
        self.NextRunTime=self.LastRunTime+self.Interval    
    
    def SetItems(self,node):
        self.Items=node  
        
    def UpdateRunTime(self):
        self.SetLastRunTime(datetime.datetime.now())
        strSql="select f_lasttime from t_thread where f_name='"+self.ShortName+"'"
        with sqlite3.connect(self.DBFile) as conn:
            rs=conn.cursor()       
            rs.execute(strSql)  
            rowCount=len(rs.fetchall())
            if rowCount>0:              
                strSql="update t_thread set f_lasttime='"+self.LastRunTime.strftime("%Y-%m-%d %H:%M:%S")+"' where f_name='"+self.ShortName+"'"                                      
            else:
                strSql="insert into t_thread (f_name,f_lasttime) values("          
                strSql+="'"+self.ShortName+"','"+self.LastRunTime.strftime("%Y-%m-%d %H:%M:%S")+"')"
            rs.execute(strSql)
            rs.close()
        #python写XML的方法实在是太弱，只能把lastruntime写进数据库了
        '''
        with open(self.ConfigFile,'r+') as fp:
            tree=ElementTree.parse(fp)
            nodes=tree.getiterator("site")
            it=nodes[0].find("./lastruntime")
            if it is not nodes:
                it.text=self.LastRunTime.strftime("%Y-%m-%d %H:%M:%S")
                tree.write(self.ConfigFile)
        '''
        return self.NextRunTime
    
    def GetLastRunTime(self):
        strSql="select count(*) from t_thread where f_name='"+self.ShortName+"'"
        with sqlite3.connect(self.DBFile) as conn:
            rs=conn.cursor()       
            rs.execute(strSql)
            rowCount=rs.fetchone()[0]
            if rowCount>0:              
                strSql="select f_lasttime from t_thread where f_name='"+self.ShortName+"'"
                rs.execute(strSql)
                fLastTime=rs.fetchone()[0]
                self.SetLastRunTime(datetime.datetime.strptime(fLastTime,"%Y-%m-%d %H:%M:%S"))
            else:
                self.SetLastRunTime(datetime.datetime.now()-self.Interval)
            rs.close()
        #logging.info("%s getlastruntime: %s \n nextruntime: %s" %(self.ShortName,self.LastRunTime.strftime("%Y-%m-%d %H:%M:%S"),self.NextRunTime.strftime("%Y-%m-%d %H:%M:%S")))
                
    def CheckRunTime(self):
        dtInterval=self.NextRunTime-datetime.datetime.now()
        return dtInterval.total_seconds()