#!/usr/bin/env python
#coding:UTF-8

import urllib2,os,datetime,re,HTMLParser,logging

LogFile="event.log"
Coding="utf-8"

def GetWeb(strUrl,strCode="utf-8",nTryTime=3):
    "抓取指定页面内容"
    content=u""
    
    while (nTryTime>0):
        try:
            req=urllib2.Request(strUrl, headers={'User-Agent' : "Mozilla/5.0 (Windows; U; Windows NT 5.1) Gecko/20070803 Firefox/1.5.0.12"})
            web=urllib2.urlopen(req)
            content=web.read().strip().decode(strCode).replace("\r","")
            nTryTime=-10
        except Exception,e:
            print strUrl
            print e
            content=u""
            nTryTime-=1
    return content

def SimpleLog(strTitle,strMemo):
    "简易日志记录"    
    global LogFile,Coding
    Now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    aInput=[u'\n[Time: '+Now+u']---------------------'
              ,u'\nTitle: '
              ,ForceCode(strTitle).encode(Coding)
              ,u'\nMemo: '
              ,ForceCode(strMemo).encode(Coding)
              ,u"\n\n"]
    
    try:
        if os.path.isfile(LogFile):
            fp=open(LogFile,'a')
        else:
            fp=open(LogFile,'w')
        fp.writelines(aInput)        
        fp.close()
    except e:
        print e
    pass

def GetXmlNodeVal(strName,node):
    "获取XML节点值"
    result=u""
    it=node.find(strName)
    if it is not None:
        if it.text is not None:
            result=ForceCode(it.text)
    return result

def GetXmlNodePropVal(strPropName,node):
    "获取XML节点属性值"
    result=u""
    if node.attrib.has_key(strPropName):
        result=ForceCode(node.attrib[strPropName])
    return result

def ForceCode(str):
    
    global Coding
    result=str
    if type(str).__name__!="unicode":
        result=str.decode(Coding)
    return result

def FilterHtml(strContent,aFilter):
    "过滤HTML代码"
    "a,table,tr,td,tbody,font,b,strong,h1-h7,hr,ul,ol,li,dd,dt,sub,sup,form,frame,iframe,object,script,style,div,span,img,p,html"
    if (aFilter is None) or len(aFilter)<1:
        return strContent
    aClearAll=["frame","iframe","object","script","style","img","br"]
    aKeepAll=["a","table","thead","tr","td","tbody","tfoot","font","b","strong","h1","h2","h3","h4","h5","h6","h7","hr","ul","ol","li","dd","dt","sub","sup","form","div","span","p","em"]
    re_cdata = re.compile('<!DOCTYPE HTML PUBLIC[^>]*>', re.I)  
    re_comment = re.compile('<!--[\s\S]*?-->',re.S) 
    re_blank_line=re.compile('\n+')
    strContent = re_cdata.sub('', strContent)    
    strContent=re_comment.sub('',strContent)   
    strContent=re_blank_line.sub('\n',strContent)  
    strContent=re.sub('\s+',' ',strContent)  
    for i in aFilter:
        if i[:3]=="all":
            f=i.split("!")
            if len(f) >1:       #处理可忽略的标签
                Skip=f[1].split(",")
                for j in Skip:
                    if j in aClearAll:
                        aClearAll.remove(j)
                    else:
                        if j in aKeepAll:
                            aKeepAll.remove(j)
            for j in aClearAll:
                strContent=FilterTag(strContent,j,True)
            for j in aKeepAll:
                strContent=FilterTag(strContent,j,False)           
            break     
        if i in aClearAll:
            strContent=FilterTag(strContent,i,True)
        else:
            strContent=FilterTag(strContent,i,False)        
    return strContent
  
def FilterTag(strContent,strTag,bClear):
    '''
    过滤HTML标签
    strContent:待过滤的内容
    strTag:需过滤的标签
    bClear:是否清除标签中的内容信息
    '''
    strReturn=strContent
    
    if bClear:
        re_data = re.compile('<\s*(?P<tag>'+strTag+'[^\s>]*?)\s*[^>]*?>[^<]*<\s*/\s*(?P=tag)\s*>', re.I|re.S)
        strContent=re_data.sub('',strContent)
        re_data = re.compile('<\s*(?P<tag>'+strTag+'[^/]*?)\s*/\s*>', re.I|re.S)
        strReturn=re_data.sub('',strContent)        
    else:
        re_f = re.compile('<\s*(?P<tag>'+strTag+'[^\s>]*?)\s*[^>]*?>', re.I|re.S)
        re_t = re.compile('<\s*/\s*'+strTag+'\s*>', re.I|re.S)
        strReturn=re_f.sub('',strReturn)
        strReturn=re_t.sub('',strReturn)
    return strReturn    

def CheckWebContent(strContent):
    "字符安全过滤"
    aFilter=[["\"","&quot;"],["<","&lt;"],[">","&rt;"],["<","&lt;"],["'","&39;"]]
    result=strContent
    
    for i in aFilter:
        result=result.replace(i[0],i[1])
    
    return result


def GetConfbak(FileName):
    
    "获取配置信息"
    SiteInfo=[]
    with open(FileName,'rt') as fp:
        tree=ElementTree.parse(fp)
        for node in tree.getiterator("site"):
            site=SiteClass("NoName","-","utf-8")
            it=node.find("./url")
            if it is not None:
                if it.text is not None:
                    site.SetUrl(it.text)
            if len(site.Url)<5:
                continue
            it=node.find("./name")
            if it is not None:
                if it.text is not None:
                    site.SetName(it.text)
            it=node.find("./code")
            if it is not None:
                if it.text is not None:
                    site.SetCode(it.text)  
            it=node.find("./proc")
            if it is not None:
                if it.text is not None:
                    site.SetProc(it.text)                      

            for nodeitems in node.getiterator("items"):
                for nodeitem in nodeitems.getchildren():
                    print nodeitem.attrib['inlink']
                    item=ItemClass()
                    item.SetName(nodeitem.tag)
                    if len(item.Name)<1:
                        continue                                      
                    it=nodeitem.find("./base")
                    if it is not None:
                        if it.text is not None:
                            item.SetBase(it.text)
                    it=nodeitem.find("./filter")
                    if it is not None:
                        if it.text is not None:
                            item.SetFilter(it.text)      
                    it=nodeitem.find("./content")
                    if it is not None:
                        if it.text is not None:
                            item.SetContent(it.text)  
                    site.Items[item.Name]=item            
            SiteInfo.append(site)
    return SiteInfo


                
if __name__ == "__main__":
    print "enigma function"    
    #动态函数测试和调用方法
    #eval("testFunc")()
    #print callable(eval("testFunc")) 