import binascii
import sys
import time
from copy import deepcopy

import serial.tools.list_ports
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton, QTextEdit, \
    QHBoxLayout, QComboBox


# 串口类
class MyDevice:

    def __init__(self):
        self.__port__ = None
        self.devices = set()  # 设备集合
        self.scores = {}  # 所有设备的分数字典，键为设备地址，值为分数列表
        self.temp_scores = {}  # 指定设备的分数字典

        # 初始化功能码
        self.Fun_ReadInfo = 0x03
        self.Fun_CheckSlave = 0x08
        self.Fun_fault = 0x10
        self.Fun_Reset = 0x01

        # 初始化信息码及错误码
        self.ErrorInfo = 0x6F
        self.header = 0x5A
        self.broad_addr = 0x00
        self.Check_Content = 0x13

        # 初始化串口链接信息
        self.baud_rate = 9600
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stop_bits = serial.STOPBITS_ONE
        self.timeout = 0.05

        # 初始化预计从机编号极值
        self.devices_num = 10

    # 更新从机编号极值
    def update_devices_num(self, num):
        self.devices_num = num

    # 连接串口
    def link(self, __baud_rate):
        # 连接第一个串口
        ports = list(serial.tools.list_ports.comports())
        if len(ports):
            port = ports[0].device
            try:
                self.__port__ = serial.Serial(port,
                                              baudrate=__baud_rate,
                                              bytesize=self.bytesize,
                                              parity=self.parity,
                                              stopbits=self.stop_bits,
                                              timeout=self.timeout)
                return [port, 0]
            except serial.SerialException as e:
                return [port, e]
        else:
            return [0, 0]

    # 串口监测
    def is_port_connected(self):
        ports = list(serial.tools.list_ports.comports())
        if self.__port__ and self.__port__.port in [port.device for port in ports]:
            return True
        return False

    # 检测下位机设备
    def check_devices(self, __addr__):
        __data__ = [self.header, __addr__, self.Fun_CheckSlave, self.Check_Content]
        __data__.append(sum(__data__))
        for p in range(5):
            self.__port__.write(__data__)
            ret_date = self.read_serial_data(self.__port__)
            if ret_date and [int(i, 16) for i in ret_date] == __data__:
                self.devices.add(__addr__)  # 维护当前在线集合
                self.scores[__addr__] = []  # 初始化设备的分数列表
                break

    # 检测指定下位机，可输入用空格隔开的序列
    def check_more_devices(self, __addresses__):
        for __addr__ in __addresses__:
            self.check_devices(__addr__)

    # 轮询所有下位机设备是否在线
    def check_all_online_devices(self):
        self.devices.clear()
        self.scores.clear()
        for __addr__ in range(self.devices_num + 1):
            self.check_devices(__addr__)
        return self.devices

    # 读串口信息
    def read_serial_data(self, __port__):
        __data__ = []
        reading = self.__port__.read(5)  # 读取串口数据
        if reading:
            hex_data = binascii.hexlify(reading).decode('utf-8')
            __data__ = [hex_data[index:index + 2] for index in range(0, len(hex_data), 2)]
            return __data__
        return []

    # 获取指定从机的分数
    def get_score(self, __addr__):
        __data__ = [self.header, self.broad_addr, self.Fun_ReadInfo, __addr__]
        __data__.append(sum(__data__))
        flag = False
        for p in range(10):
            self.__port__.write(__data__)
            ret_data = self.read_serial_data(self.__port__)
            if ret_data:
                ret_data = [int(i, 16) for i in ret_data]
                self.devices.add(__addr__)
                if ret_data[1] == __addr__ and ret_data[4] == sum(
                        ret_data[:4]) and ret_data[3] != self.ErrorInfo:
                    if ret_data[3] <= 100:
                        self.scores[__addr__] = ret_data[3]
                        return ret_data[3]
                    else:
                        return -2
                elif ret_data[2] == self.Fun_ReadInfo and ret_data[3] == self.ErrorInfo:
                    return -3  # 从机未确认编号
                elif ret_data[3] == self.ErrorInfo:
                    return -2  # 分数大于100或者未确认分数
                else:
                    return -1  # 数据校验错误
            if p == 9:
                flag = True
        if flag:
            return -3  # 从机无回应

    # 分别获取指定从机序列的分数
    def get_more_score(self, __addresses__):
        self.temp_scores.clear()
        for __addr__ in __addresses__:
            ret = self.get_score(__addr__)
            self.temp_scores[__addr__] = ret
        return self.temp_scores

    # 获取所有在线从机的分数
    def get_all_score(self):  # 获取所有在线从机分数
        for __device__ in self.devices:
            ret = self.get_score(__device__)
            self.scores[__device__] = ret
        return self.scores

    # 获得当前已知分数的最大值
    def get_highest_score(self):
        if self.scores:
            highest = max(scores for scores in self.scores.values())  # 计算最高分
            return highest
        else:
            return -1

    # 获得当前已知分数的最小值
    def get_lowest_score(self):
        if self.scores:
            res = deepcopy(self.scores)
            for _id, score in res.items():
                if score < 0:
                    del self.scores[_id]
            lowest = min(scores for scores in self.scores.values())  # 计算最低分
            return lowest
        else:
            return -1

    # 获得当前已知分数的平均值
    def get_average_score(self):
        if self.scores:
            res = deepcopy(self.scores)
            for _id, score in res.items():
                if score < 0:
                    del self.scores[_id]
            total_scores = [scores
                            for scores in self.scores.values()]  # 所有分数的列表
            average = sum(total_scores) / len(
                total_scores) if total_scores else 0  # 计算平均分
            return average
        else:
            return -1

    # 获得给出指定分数的从机序列
    def get_device_ids_with_score(self, score):
        device_ids = []
        for device_id, device_score in self.scores.items():
            if device_score == score:
                device_ids.append(device_id)
        return device_ids

    # 复位从机
    def ReSet(self):
        __data__ = [self.header, self.broad_addr, self.Fun_Reset, 0x00]
        __data__.append(sum(__data__))
        for p in range(10):
            self.__port__.write(__data__)

    # 关闭串口
    def Close(self):
        self.__port__.close()


# 图形化窗口
class MyWindow(QWidget):

    def __init__(self, _master):
        super().__init__()
        self.baud_rate = 9600

        # 初始化波特率选择部分
        self.baud_rate_label = QLabel("波特率:")
        self.baud_rate_combo = QComboBox()
        self.baud_rate_combo.addItem("50")
        self.baud_rate_combo.addItem("75")
        self.baud_rate_combo.addItem("110")
        self.baud_rate_combo.addItem("134")
        self.baud_rate_combo.addItem("150")
        self.baud_rate_combo.addItem("200")
        self.baud_rate_combo.addItem("300")
        self.baud_rate_combo.addItem("600")
        self.baud_rate_combo.addItem("1200")
        self.baud_rate_combo.addItem("1800")
        self.baud_rate_combo.addItem("2400")
        self.baud_rate_combo.addItem("4800")
        self.baud_rate_combo.addItem("9600")
        self.baud_rate_combo.addItem("19200")
        self.baud_rate_combo.addItem("38400")
        self.baud_rate_combo.addItem("57600")
        self.baud_rate_combo.addItem("115200")
        self.baud_rate_combo.addItem("230400")
        self.baud_rate_combo.addItem("460800")
        self.baud_rate_combo.addItem("500000")
        self.baud_rate_combo.addItem("576000")
        self.baud_rate_combo.addItem("921600")
        self.baud_rate_combo.addItem("1000000")
        self.baud_rate_combo.addItem("1152000")
        self.baud_rate_combo.addItem("1500000")
        self.baud_rate_combo.addItem("2000000")
        self.baud_rate_combo.addItem("2500000")
        self.baud_rate_combo.addItem("3000000")
        self.baud_rate_combo.addItem("3500000")
        self.baud_rate_combo.addItem("4000000")
        self.baud_rate_combo.setCurrentIndex(12)
        self.baud_rate_combo.currentTextChanged.connect(self.baud_rate_changed)

        # 初始化串口连接监测计时器
        self.check_port_timer = None

        # 初始化从机编号最大值，轮询时从0轮询至最大值
        self.devices_Num_label = QLabel("请输入从机编号最大值:")
        self.devices_Num_edit = QLineEdit()
        self.devices_Num_edit.setPlaceholderText("无输入或未确认则默认10")
        self.devices_Num_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.confirm = QPushButton("确认")

        # 输入指定查询的从机编号
        self.devices_id_label = QLabel("输入从机编号:")
        self.text_edit = QLineEdit()
        self.text_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.query = QPushButton("查询")

        # 功能键
        self.update_all_online_devices = QPushButton("更新当前在线从机")
        self.update_all_online_devices_score = QPushButton("查询当前在线从机分数")
        self.highest_score = QPushButton("查看最高分")
        self.lowest_score = QPushButton("查看最低分")
        self.average_score = QPushButton("查看平均分")
        self.reset = QPushButton("复位")
        self.clear = QPushButton("清屏")
        self.unlink = QPushButton("断开连接")
        self.link = QPushButton("连接主机")
        self.cLose = QPushButton("断开连接并退出")
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.master = _master

        # 初始化UI
        self.initUI()

    # 排列各个组件
    def initUI(self):
        self.setWindowTitle("基于RS-485总线的多机交互的分数查询工具")
        self.setGeometry(1300, 300, 500, 500)

        # 波特率选择栏
        baud_layout = QHBoxLayout()
        baud_layout.addWidget(self.baud_rate_label)
        baud_layout.addWidget(self.baud_rate_combo)

        # 输入从机编号最大值栏
        devices_num_layout = QHBoxLayout()
        devices_num_layout.addWidget(self.devices_Num_label)
        devices_num_layout.addWidget(self.devices_Num_edit)
        devices_num_layout.addWidget(self.confirm)

        # 标签、文本框和查询
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.devices_id_label)
        h_layout.addWidget(self.text_edit)
        h_layout.addWidget(self.query)

        # 查询
        update_layout = QHBoxLayout()
        update_layout.addWidget(self.update_all_online_devices)
        update_layout.addWidget(self.update_all_online_devices_score)

        # 分数处理
        score_layout = QHBoxLayout()
        score_layout.addWidget(self.highest_score)
        score_layout.addWidget(self.lowest_score)
        score_layout.addWidget(self.average_score)

        # 复位和清屏
        clean_layout = QHBoxLayout()
        clean_layout.addWidget(self.reset)
        clean_layout.addWidget(self.clear)

        # 连接与断开连接
        link_layout = QHBoxLayout()
        link_layout.addWidget(self.link)
        link_layout.addWidget(self.unlink)

        # 退出
        cLose_layout = QHBoxLayout()
        cLose_layout.addWidget(self.cLose)

        # 水平排列上述块
        v_layout = QVBoxLayout()
        v_layout.addLayout(h_layout)
        v_layout.addLayout(update_layout)
        v_layout.addLayout(score_layout)
        v_layout.addLayout(clean_layout)
        v_layout.addLayout(baud_layout)
        v_layout.addLayout(devices_num_layout)
        v_layout.addLayout(link_layout)
        v_layout.addLayout(cLose_layout)
        v_layout.addWidget(self.output)

        # 设置窗口主布局
        self.setLayout(v_layout)

        # 链接相关函数
        self.confirm.clicked.connect(self._update_devices_num)
        self.query.clicked.connect(self.queryScore)
        self.update_all_online_devices.clicked.connect(self.update_Devices)
        self.update_all_online_devices_score.clicked.connect(self.update_Score)
        self.highest_score.clicked.connect(self.highest_Score)
        self.lowest_score.clicked.connect(self.lowest_Score)
        self.average_score.clicked.connect(self.average_Score)
        self.reset.clicked.connect(self.reSet)
        self.clear.clicked.connect(self.Clear)
        self.unlink.clicked.connect(self.unLink)
        self.link.clicked.connect(self.Link)
        self.cLose.clicked.connect(self.Close)

        # 检查串口连接状态并设置按钮可见性
        self.check_port_connection()

    # 设置按钮可见性，主要是连接成功后的显示
    def set_button_visibility(self, visible):
        self.devices_id_label.setVisible(visible)
        self.text_edit.setVisible(visible)
        self.query.setVisible(visible)
        self.update_all_online_devices.setVisible(visible)
        self.update_all_online_devices_score.setVisible(visible)
        self.highest_score.setVisible(visible)
        self.lowest_score.setVisible(visible)
        self.average_score.setVisible(visible)
        self.reset.setVisible(visible)
        self.clear.setVisible(visible)
        self.unlink.setVisible(visible)
        self.cLose.setVisible(visible)

    # 设置按钮可见，主要是连接成功前的组件
    def set_combo_visibility(self, visible):
        self.baud_rate_label.setVisible(visible)
        self.baud_rate_combo.setVisible(visible)
        self.devices_Num_label.setVisible(visible)
        self.devices_Num_edit.setVisible(visible)
        self.confirm.setVisible(visible)

    # 使组件不可见
    def set_button_unable(self):
        self.set_button_visibility(False)

    # 使组件可见
    def set_button_able(self):
        self.set_button_visibility(True)

    # 使组件不可见
    def set_combo_unable(self):
        self.set_combo_visibility(False)

    # 使组件可见
    def set_combo_able(self):
        self.set_combo_visibility(True)

    # 设置连接相关组建可见性
    def set_link(self, visible):
        self.link.setVisible(visible)
        self.unlink.setVisible(not visible)

    # 使组件可见
    def set_link_able(self):
        self.set_link(True)

    # 使组件不可见
    def set_link_unable(self):
        self.set_link(False)

    # 监测串口状态，修改组件可见性
    def check_port_connection(self):
        if not self.master.is_port_connected():
            self.set_button_unable()
            self.set_combo_able()
            self.set_link_able()

    # 修改连接参数波特率
    def baud_rate_changed(self, text):
        self.baud_rate = int(text)

    # 向输出栏输出，并立即刷新GUI，避免缓存区引起的输出延迟
    def _output(self, *args):
        message = " ".join(str(arg) for arg in args)
        self.output.append(message)
        QApplication.processEvents()

    # 设置从机编号极值
    def _update_devices_num(self):
        _num = self.devices_Num_edit.text()
        _num = _num.split()
        try:
            if len(_num) <= 0:
                self._output("未输入，请重新输入")
            elif len(_num) > 1:
                self._output("参数过多，请重新输入")
            else:
                self.master.update_devices_num(int(_num[0]))
                self._output("设置成功")
                return
        except ValueError:
            self._output("非法字符，请重新输入")
            return

    # 查询指定从机序列分数
    def queryScore(self):
        addr = self.text_edit.text()
        addr = addr.split()
        try:
            addr = [int(address) for address in addr]
            for a in addr:
                if a < 0 or a > 255:
                    self._output("地址超出有效范围，请重新输入")
                    return
        except ValueError:
            self._output("地址输入错误，请重新输入")
            return
        scores = self.master.get_more_score(addr)
        if scores:
            sorted_scores = sorted(scores.items(), key=lambda x: x[0])
            self._output("指定从机分数：")
            for device_id, score in sorted_scores:
                if score == -1:
                    self._output("从机 {" + str(device_id) + "} 数据校验错误")
                elif score == -2:
                    self._output("从机 {" + str(device_id) + "} 分数大于100或未确认分数")
                elif score == -3:
                    self._output("从机 {" + str(device_id) + "} 未确认自身编号")
                else:
                    self._output("从机 {" + str(device_id) + "} 分数：" +
                                 str(score))
        else:
            self._output("没有查询到从机分数")

    # 更新当前在线从机序列
    def update_Devices(self):
        online_devices = self.master.check_all_online_devices()
        if online_devices:
            self._output("在线下位机编号：")
            devices = [device for device in online_devices]
            self._output(devices)
        else:
            self._output("没有检测到在线下位机")
        return

    # 更新当前在线从机序列的分数
    def update_Score(self):
        scores = self.master.get_all_score()
        if scores:
            sorted_scores = sorted(scores.items(), key=lambda x: x[0])
            self._output("所有在线从机分数：")
            for device_id, score in sorted_scores:
                if score == -1:
                    self._output("从机 {" + str(device_id) + "} 数据校验错误")
                elif score == -2:
                    self._output("从机 {" + str(device_id) + "} 分数大于100或未确认分数")
                elif score == -3:
                    self._output("从机 {" + str(device_id) + "} 未确认自身编号")
                else:
                    self._output("从机 {" + str(device_id) + "} 分数：" +
                                 str(score))
        else:
            self._output("没有查询到从机分数")

    # 计算最高分并列出给出最高分的从机序列
    def highest_Score(self):
        highest_score = self.master.get_highest_score()
        if highest_score == -1:
            self._output("请先查询从机分数")
        else:
            device_ids = self.master.get_device_ids_with_score(highest_score)
            output_message = "给出最高分的从机："
            output_message += "".join(
                str(device_id) for device_id in device_ids)
            self._output("最高分：", str(highest_score))
            self._output(output_message)

    # 计算最低分并列出给出最低分的从机序列
    def lowest_Score(self):
        lowest_score = self.master.get_lowest_score()
        if lowest_score == -1:
            self._output("请先查询从机分数")
        else:
            device_ids = self.master.get_device_ids_with_score(lowest_score)
            output_message = "给出最低分的从机："
            output_message += "".join(
                str(device_id) for device_id in device_ids)
            self._output("最低分：", str(lowest_score))
            self._output(output_message)

    # 计算平均分并列出给出平均分的从机序列
    def average_Score(self):
        average_score = self.master.get_average_score()
        if average_score == -1:
            self._output("请先查询从机分数")
        else:
            self._output("平均分：" + str(average_score))

    # 复位
    def reSet(self):
        self.master.ReSet()
        self._output("已发送复位指令")

    # 清理输出栏
    def Clear(self):
        self.output.clear()

    # 关闭串口并退出
    def Close(self):
        self.master.Close()
        self.close()

    # 与串口断开连接
    def unLink(self):
        ret = self.master.Close()
        if ret:
            self._output("与端口断开连接失败。")
        else:
            self._output("成功与端口断开连接。")
            self.set_button_unable()
            self.set_combo_able()
            self.set_link_able()

    # 连接串口
    def Link(self):
        # 设置最大尝试次数
        max_attempts = 6
        attempt = 1
        while attempt < max_attempts:
            self._output("第 " + str(attempt) + " 次尝试连接...")
            ret = self.master.link(self.baud_rate)
            if ret[0] == 0:
                self._output("无可用端口")
            elif ret[1] == 0:
                self._output("端口 " + ret[0] + " 连接成功")
                self.set_button_able()
                self.set_combo_unable()
                self.set_link_unable()
                break
            else:
                self._output("端口 " + ret[0] + " 连接失败: " + str(ret[1]))
            attempt += 1
            time.sleep(1)
        if attempt == max_attempts:
            self._output("已达最大连接次数，连接失败。")
            exit(0)

    # 重写show()方法，以控制显示可见行，当串口被拔出后回到连接界面
    def showEvent(self, event):
        super().showEvent(event)
        self.check_port_timer = QtCore.QTimer()
        self.check_port_timer.timeout.connect(self.check_port_connection)
        self.check_port_timer.start(1000)  # 每1秒检查一次串口连接状态

    # 重写hide()方法，同上
    def hideEvent(self, event):
        super().hideEvent(event)
        self.check_port_timer.stop()


# 主程序
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 创建串口实例
    master = MyDevice()
    # 创建UI实例
    window = MyWindow(master)
    window.show()

    sys.exit(app.exec_())
