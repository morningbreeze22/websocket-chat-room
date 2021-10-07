#coding:utf-8

import numpy as np
import tornado.web
import tornado.ioloop
import tornado.httpserver
import tornado.options
import tornado.websocket
from tornado.options import options, define
from tornado.web import RequestHandler, MissingArgumentError
import logging
import json
import datetime

roomlist=set()   #房间列表
userlist=[]      #用户列表
records=[]       #对话记录
recentuser=""

chathistory = {}    #记录曾加入某房间的所有用户
timestamps =[]     #记录用户进入和离开房间的时间

class Record:
# 用于保存记录
    def __init__(self, room, message, user, date):
        self.room=room
        self.message = message
        self.user = user
        self.date = date

    def to_dict(self):
        return {
            'room' : str(self.room),
            'message' : str(self.message),
            'username': str(self.user),
            'date': str(self.date)
        }

    def username(self):
        return str(self.user)

    def roomname(self):
        return str(self.room)
    
    def messageinfo(self):
        return str(self.message)

    def dateinfo(self):
        return self.date

class history:
    #用于保存历史#
    def __init__(self,room,user,start=datetime.datetime.now(),end=datetime.datetime(1998, 1, 1, 1, 1, 1, 111111)):
        #end初始值采用特殊值
        self.room=room
        self.user=user
        self.start=start
        self.end=end

    def set_end(self,end):
        self.end=end
    
    def get_start(self):
        return self.start

    def get_end(self):
        return self.end

    def get_room(self):
        return self.room

    def get_user(self):
        return self.user

    def get_info(self):
        return str(self.user)+'at'+str(self.room)+'start:'+str(self.start)+'end'+str(self.end)


class ChatHome(object):
   
    #处理websocket 服务器与客户端交互#
  
    chatRegister = {}    #用于保存房间内的用户
    
    def register(self, newuser):
        #websocket中open对应的方法，处理加入房间的用户
        home = str(newuser.get_argument('n'))     #获取所在聊天室
        name = str(newuser.get_argument('u'))     #获取用户名
        time = datetime.datetime.now()
        if home in self.chatRegister:              #将用户添加到房间中
            self.chatRegister[home].append(newuser)
        else:
            self.chatRegister[home] = [newuser]
        if home in chathistory:               #记录某房间内所有历史用户
            chathistory[home].append(name)
        else:
            chathistory[home]=[name]
        words=name+"加入了本聊天室"
        message=Record(home,words,"systeminfo",time)   #系统提示用户进入聊天室的记录
        stamp=history(home,name,time)    #记录某用户进入某房间的时间点
        timestamps.append(stamp)
        records.append(message)
        self.sendmessage(home, message.to_dict())

    def unregister(self, lefter):

        #websocket中onclose对应的方法，删除聊天室内对应的用户并记录用户离开的时间

        home = str(lefter.get_argument('n'))
        name = str(lefter.get_argument('u'))
        time = datetime.datetime.now()
        self.chatRegister[home].remove(lefter)   #从房间中删除用户
        words=name+"离开了本聊天室"
        message=Record(home,words,"systeminfo",time)  #系统提示用户离开聊天室的记录
        records.append(message)
        for stamp in timestamps:
            if stamp.get_room()==home and stamp.get_user()==name and stamp.get_end()==datetime.datetime(1998, 1, 1, 1, 1, 1, 111111):
                stamp.set_end(time)     #找到对应用户进入房间的记录，添加离开时间
        if self.chatRegister[home]:     
            self.sendmessage(home, message.to_dict())

    def callbackNews(self, sender, message):
       
        #处理客户端提交的信息，封装后发送给对应聊天室内所有的用户
        
        home = str(sender.get_argument('n'))
        user = str(sender.get_argument('u'))
        time = datetime.datetime.now()
        the_record=Record(home,message,user,time)
        records.append(the_record)
        self.sendmessage(home,the_record.to_dict())

    def sendmessage(self, home, message):
        
        # 将消息返回给对应聊天室的所有在线用户

        for user in self.chatRegister[home]:
            user.write_message(json.dumps(message))



define("port", default=8000, help="run on the given port", type=int)


class webchat(tornado.websocket.WebSocketHandler):

    def open(self):    #新建连接时调用的函数
        roomname=self.get_argument('n')
        roomname=str(roomname)
        recentuser=str(self.get_argument('u'))
        the_port=str(self.get_argument('p'))  #获取端口号
        past_message=""

        #不同的用户做不同操作
        if roomname in chathistory:
            if recentuser in chathistory[roomname]:
                #历史用户，根据record和timestamp中记录的时间找到该用户对应的历史记录并发送
                historyrecords=[]
                now=datetime.datetime.now()

                for stamp in timestamps:
                    if stamp.get_room()==roomname and stamp.get_user()==recentuser: 
                        starttime=stamp.get_start()     #找到该用户某次进入和离开聊天室的时间
                        endtime=stamp.get_end()
                        for therecord in records:
                            if therecord.dateinfo()<endtime and therecord.dateinfo()>=starttime:
                                self.write_message(json.dumps(therecord.to_dict()))   #将用户在线时间段的信息发送
                past_message="欢迎回到"+roomname
                welcome=Record(roomname,past_message,"systeminfo",str(now))
                self.write_message(json.dumps(welcome.to_dict()))      #向用户发送消息
                self.application.chathome.register(self)    #记录连接和时间戳
            else:
                #新加入已创建房间的用户
                chathistory[roomname].append(recentuser)
                past_message="欢迎来到"+roomname
                welcome=Record(roomname,past_message,"systeminfo",str(datetime.datetime.now()))
                self.write_message(json.dumps(welcome.to_dict()))      #向用户发送首次消息
                self.application.chathome.register(self)    #记录连接和时间戳
        else:
            #新建房间的第一个用户
            chathistory[roomname]=[recentuser]
            past_message="欢迎来到新房间"+roomname
            welcome=Record(roomname,past_message,"systeminfo",str(datetime.datetime.now()))
            self.write_message(json.dumps(welcome.to_dict()))      #向新房间的第一个用户发送首次消息
            self.application.chathome.register(self)    #记录连接和时间戳
    
    def on_close(self):
        self.application.chathome.unregister(self)  #删除某用户的连接

    def on_message(self, message):
        self.application.chathome.callbackNews(self, message)   #处理客户端提交的最新消息

class ReturnHandler(RequestHandler):       #聊天室返回选择聊天室的界面
    def post(self):
        the_port=str(self.request.host)
        the_port=the_port.split(":")[1]
        name=self.get_argument('name')
        name=str(name)
        recentuser=name
        self.render('chatroom.html', user=recentuser,port=the_port,rooms=roomlist)


class ExitHandler(RequestHandler):
    def post(self):
        #从用户列表删除某用户
        name=self.get_argument('user')
        userlist.remove(name)
        self.render('login.html', note="")

'''class ChatHandler(RequestHandler):      #测试用，后来改成websocket类
    def post(self):
        content=str(self.get_argument('send'))
        print(content)
        roomlist.append(newroom)
        self.render('chat.html', user=recentuser)'''

class JoinHandler(RequestHandler):   #处理用户创建或加入房间的请求
    def post(self):
        roomname=self.get_argument('roomname')
        roomname=str(roomname)
        roomlist.add(roomname)    #添加房间列表的集合中
        recentuser=str(self.get_argument('user'))
        the_port=str(self.get_argument('port'))
        self.render('inhome.html', u=recentuser,n=roomname,p=the_port)  #渲染聊天室页面

'''class CreateHandler(RequestHandler):   #创建新房间，在本实验中功能与joinhandler相同因此合并
    def post(self):
        newroom=str(self.get_argument('newroomname'))
        recentuser=str(self.get_argument('user'))
        the_port=str(self.get_argument('port'))
        chathistory[newroom]=[]
        self.render('inhome.html', u=recentuser,n=newroom,p=the_port)'''

class RoomHandler(RequestHandler):    #判断用户是否重名
    def post(self):
        the_port=str(self.request.host)
        the_port=the_port.split(":")[1]
        name=self.get_argument('name')
        name=str(name)
        recentuser=name
        if name in userlist:          #若已有同名用户登录，则返回登录界面并给出提示信息
            self.render('login.html', note="该昵称已被使用，")
        else:
            userlist.append(name)     #若用户名符合条件，则进入选择房间的界面
            self.render('chatroom.html', user=recentuser,port=the_port,rooms=roomlist)

class LoginHandler(RequestHandler):    #登录
    def get(self):
        self.render('login.html', note="")

    def post(self):
        pass


if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = tornado.web.Application(
        [

            (r"/", LoginHandler),
            (r"/room",RoomHandler),
            (r"/exit",ExitHandler),
            (r"/join",JoinHandler),
            (r'/newwebchat/', webchat),
            #(r"/update",ChatHandler),
            (r"/return",ReturnHandler),
        ])
    app.chathome=ChatHome()
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(8000)
    http_server.listen(8001)
    tornado.ioloop.IOLoop.current().start()
