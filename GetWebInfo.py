#!/usr/bin/env python
#coding:UTF-8
#ver 1.0

import os,datetime,re,hashlib,urlparse,sqlite3,pickle,urllib,urllib2,sys,Queue,string,random,time
from xml.etree import ElementTree
from EnigmaClass import ItemClass,SiteClass,getRemoteFile
from GetInfo import getInfo
import EnigmaFunc

SiteInfo={}     #站点信息
ContStore={}    #抓取内容缓存
DBF=""          #抓取信息本地暂存数据库文件名
MaxThreadNumb=1 #最大抓取进程数
CheckEndTime=datetime.timedelta(seconds=120)    #终止程序标志检测周期
CheckEndFlagFile="stop.flg" #终止程序标志文件
AppPath=os.path.split(os.path.realpath(__file__))[0]+os.sep     #程序所在目录

def GetConf(FileName):
    "获取配置信息"
    global DBF,MaxThreadNumb,CheckEndTime,CheckEndFlagFile
    SiteInfo={} 
    with open(FileName,'r+') as fp:
        tree=ElementTree.parse(fp)
        nodes=tree.getiterator("set")
        MaxThreadNumb=string.atoi(EnigmaFunc.GetXmlNodeVal("./thread",nodes[0]))
        CheckEnd=string.atoi(EnigmaFunc.GetXmlNodeVal("./checkend",nodes[0]))
        #检测周期不能小于5秒
        if CheckEnd<5:
            CheckEnd=120
        CheckEndTime=datetime.timedelta(seconds=CheckEnd)   
        checkEndFlag=EnigmaFunc.GetXmlNodeVal("./checkendflag",nodes[0])
        if len(checkEndFlag)<1:
            CheckEndFlagFile=AppPath+"stop.flg"
        else:
            CheckEndFlagFile=AppPath+checkEndFlag
        DBF=EnigmaFunc.GetXmlNodeVal("./database",nodes[0])
        tf=0
        if len(DBF)>1:
            DBF=AppPath+DBF
            if os.path.isfile(DBF):
                tf=1
        if 0==tf:
            return False
        dir=AppPath+EnigmaFunc.GetXmlNodeVal("./directory",nodes[0])
    if os.path.isdir(dir):
        list= os.listdir(dir)
        for i in list:
            filepath = os.path.join(dir,i)
            if os.path.isfile(filepath):
                fex=filepath.split(".")
                if len(fex)>1:
                    fext=fex[len(fex)-1].lower().strip()
                    if cmp(fext,"xml")==0:
                        GetSiteConf(filepath)         
    return True

def GetSiteConf(FileName):
    "获取配置信息"
    global SiteInfo,DBF  
    with open(FileName,'rt') as fp:
        tree=ElementTree.parse(fp)
        for node in tree.getiterator("site"):             
            strName=EnigmaFunc.GetXmlNodeVal("./name",node)             
            strState=EnigmaFunc.GetXmlNodeVal("./state",node)
            if strState!="run" and strState!="test":
                EnigmaFunc.SimpleLog("站点暂停抓取",strName+u"状态代码："+strState)
                continue                   
            strUrl=EnigmaFunc.GetXmlNodeVal("./url",node)            
            if len(strUrl)<5:
                EnigmaFunc.SimpleLog("Warning"," URL无效,跳过此站")
                continue     
            strPostUrl=EnigmaFunc.GetXmlNodeVal("./posturl",node)
            if len(strPostUrl)<5:
                EnigmaFunc.SimpleLog("Warning",strPostUrl+u" 链接无效")
                continue
            postArg={}
            it=node.find("postarg")
            if it is not None:
                for i in it.getchildren():
                    postArg[i.tag]=i.text
            strShortName=EnigmaFunc.GetXmlNodeVal("./shortname",node)  
            nInterval=int(EnigmaFunc.GetXmlNodeVal("./interval",node))                 
            nCheckDuplicate=int(EnigmaFunc.GetXmlNodeVal("./checkDuplicate",node))                 
            strCode=EnigmaFunc.GetXmlNodeVal("./code",node)
            if len(strCode)<1:
                strCode=EnigmaFunc.Coding     #站点编码
            site=SiteClass(strName,strShortName,strUrl,strCode,strState,strPostUrl,DBF,(nCheckDuplicate>0),nInterval)
            site.SetPostArg(postArg)
            site.SetConfigFile(FileName)
            site.SetItems(node.find("items"))
            site.GetLastRunTime()
            SiteInfo[strShortName]=site
        return True

def main():
    "主程序"
            
    global SiteInfo,AppPath,DBF,MaxThreadNumb,CheckEndTime,CheckEndFlagFile
    if not GetConf(AppPath+"config.xml"):     
        print "配置文件读取失败，程序退出！"
        return
    SiteNumb=len(SiteInfo)
    if SiteNumb<1:
        print "没有抓取项目，程序退出！"
        return
    logDirPath=AppPath+"logs"
    if os.path.exists(logDirPath):
        if not os.path.isdir(logDirPath):
            print "无法创建日志目录，程序退出！"
    else:
        os.makedirs(logDirPath)
    print "SiteNumb=%d" % (SiteNumb)
    print "MaxThreadNumb=%d" % (MaxThreadNumb)
    nextRunSite=getNextRun(SiteInfo)
    running=[]
    lastCheckEnd=datetime.datetime.now()+CheckEndTime
    checkInterval=CheckEndTime.total_seconds()
    while len(nextRunSite)>0:
        sleepTime=SiteInfo[nextRunSite].CheckRunTime()
        while checkInterval<=sleepTime:
            print "we will sleep %d s" %(checkInterval)
            time.sleep(checkInterval)
            sleepTime-=checkInterval
            if lastCheckEnd<=datetime.datetime.now():
                if CheckEndFlag():
                    print "检测到结束标志，程序正在退出."
                    sleepTime=0
                    nextRunSite=""
                    break
                else:
                    lastCheckEnd=datetime.datetime.now()+CheckEndTime
        if sleepTime>0:
            print "sleep %f" %(sleepTime)
            time.sleep(sleepTime)
        if lastCheckEnd<=datetime.datetime.now():
            if CheckEndFlag():
                print "检测到结束标志，程序正在退出"
                sleepTime=0
                nextRunSite=""
                break
            else:
                lastCheckEnd=datetime.datetime.now()+CheckEndTime
        if len(nextRunSite)>0:
            if len(running)>=MaxThreadNumb:
                #FIFO获取等待线程
                sn=running.pop(0)
                print "#%s 正在等待 #%s 执行完毕" %(nextRunSite,sn.getName())
                sn.join()
            print "%s start" % (nextRunSite)
            RunThread=getInfo(SiteInfo[nextRunSite].ShortName,SiteInfo[nextRunSite])
            running.append(RunThread)
            RunThread.start()
            SiteInfo[nextRunSite].UpdateRunTime()
            nextRunSite=getNextRun(SiteInfo)
    for i in running:
        if i.is_alive():
            i.join()
    print "程序运行结束"     

def CheckEndFlag():
    global CheckEndFlagFile
    bReturn=False
    if os.path.exists(CheckEndFlagFile):
        os.remove(CheckEndFlagFile)
        bReturn=True
    return bReturn

def getNextRun(site):
    nextRunTime=99999999999
    for i in site.keys():
        ti=site[i].CheckRunTime()
        if ti<nextRunTime:
            nextRunTime=ti
            nextRunSite=site[i].ShortName
    return nextRunSite
     
if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding('utf-8')
    main()
