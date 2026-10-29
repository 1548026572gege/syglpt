# -*- coding: utf-8 -*-
"""数据库模型：对应设计文档第 5 章核心数据表。"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """用户表：教师 / 实验管理员 / 系统管理员"""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")  # teacher / admin / sysadmin
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    classes = db.Column(db.String(200))  # 任教班级，逗号分隔
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "name": self.name,
            "phone": self.phone,
            "classes": self.classes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class Instrument(db.Model):
    """仪器台账表"""
    __tablename__ = "instruments"
    id = db.Column(db.Integer, primary_key=True)
    state_code = db.Column(db.String(50))           # 国资系统编号
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 仪器编号
    name = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100))               # 型号
    spec = db.Column(db.String(200))                # 规格
    unit = db.Column(db.String(20))                 # 单位
    category = db.Column(db.String(50))             # 分类
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)          # 单价（元）
    requirement = db.Column(db.String(20))          # 配备要求（必配/选配）
    amount = db.Column(db.Float, default=0)         # 金额（元）
    location = db.Column(db.String(100))            # 存放位置
    status = db.Column(db.String(20), default="正常")  # 正常/借出/维修中/损耗/报废
    purchase_date = db.Column(db.String(20))        # 购置日期
    remark = db.Column(db.String(300))              # 备注
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "state_code": self.state_code,
            "code": self.code,
            "name": self.name,
            "model": self.model,
            "spec": self.spec,
            "unit": self.unit,
            "category": self.category,
            "quantity": self.quantity,
            "price": self.price,
            "requirement": self.requirement,
            "amount": self.amount,
            "location": self.location,
            "status": self.status,
            "purchase_date": self.purchase_date,
            "remark": self.remark,
        }


class Reservation(db.Model):
    """实验预约表"""
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    lab_name = db.Column(db.String(100), nullable=False)      # 实验室
    experiment_name = db.Column(db.String(200), nullable=False)
    class_name = db.Column(db.String(100))                    # 参与班级
    student_count = db.Column(db.Integer)                     # 学生人数
    group_count = db.Column(db.Integer)                       # 分组数
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    remark = db.Column(db.Text)
    status = db.Column(db.String(20), default="待审核")  # 待审核/已通过/已驳回/已完成/已取消
    review_comment = db.Column(db.String(300))                # 审核意见
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.now)

    teacher = db.relationship("User", foreign_keys=[teacher_id])

    def to_dict(self):
        fmt = "%Y-%m-%d %H:%M"
        return {
            "id": self.id,
            "teacher_id": self.teacher_id,
            "teacher_name": self.teacher.name if self.teacher else "",
            "lab_name": self.lab_name,
            "experiment_name": self.experiment_name,
            "class_name": self.class_name,
            "student_count": self.student_count,
            "group_count": self.group_count,
            "start_time": self.start_time.strftime(fmt) if self.start_time else None,
            "end_time": self.end_time.strftime(fmt) if self.end_time else None,
            "remark": self.remark,
            "status": self.status,
            "review_comment": self.review_comment,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class BorrowRecord(db.Model):
    """仪器借用记录表"""
    __tablename__ = "borrow_records"
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey("instruments.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    purpose = db.Column(db.String(300))                       # 用途
    expect_return_time = db.Column(db.DateTime)               # 预计归还时间
    borrow_time = db.Column(db.DateTime)                      # 实际借出时间
    return_time = db.Column(db.DateTime)                      # 归还时间
    return_status = db.Column(db.String(50))                  # 归还时仪器状态说明
    status = db.Column(db.String(20), default="申请中")   # 申请中/已借出/已归还/已驳回
    created_at = db.Column(db.DateTime, default=datetime.now)

    instrument = db.relationship("Instrument")
    teacher = db.relationship("User", foreign_keys=[teacher_id])

    def to_dict(self):
        fmt = "%Y-%m-%d %H:%M"
        overdue = False
        if self.status == "已借出" and self.expect_return_time and datetime.now() > self.expect_return_time:
            overdue = True
        return {
            "id": self.id,
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument.name if self.instrument else "",
            "instrument_code": self.instrument.code if self.instrument else "",
            "teacher_id": self.teacher_id,
            "teacher_name": self.teacher.name if self.teacher else "",
            "quantity": self.quantity,
            "purpose": self.purpose,
            "expect_return_time": self.expect_return_time.strftime(fmt) if self.expect_return_time else None,
            "borrow_time": self.borrow_time.strftime(fmt) if self.borrow_time else None,
            "return_time": self.return_time.strftime(fmt) if self.return_time else None,
            "return_status": self.return_status,
            "status": self.status,
            "overdue": overdue,
        }


class RepairRecord(db.Model):
    """仪器维修记录表"""
    __tablename__ = "repair_records"
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey("instruments.id"), nullable=False)
    fault_desc = db.Column(db.Text, nullable=False)           # 故障描述
    report_time = db.Column(db.DateTime, default=datetime.now)  # 上报时间
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    repair_time = db.Column(db.DateTime)                      # 维修时间
    repair_result = db.Column(db.String(300))                 # 维修结果
    cost = db.Column(db.Float, default=0)                     # 维修费用
    status = db.Column(db.String(20), default="报修中")   # 报修中/维修中/已完成/报废

    instrument = db.relationship("Instrument")
    reporter = db.relationship("User")

    def to_dict(self):
        fmt = "%Y-%m-%d %H:%M"
        return {
            "id": self.id,
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument.name if self.instrument else "",
            "instrument_code": self.instrument.code if self.instrument else "",
            "fault_desc": self.fault_desc,
            "report_time": self.report_time.strftime(fmt) if self.report_time else None,
            "reporter_name": self.reporter.name if self.reporter else "",
            "repair_time": self.repair_time.strftime(fmt) if self.repair_time else None,
            "repair_result": self.repair_result,
            "cost": self.cost,
            "status": self.status,
        }


class LossRecord(db.Model):
    """仪器损耗记录表"""
    __tablename__ = "loss_records"
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey("instruments.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    loss_time = db.Column(db.DateTime, default=datetime.now)  # 损耗时间
    reason = db.Column(db.String(300))                        # 损耗原因
    responsible = db.Column(db.String(50))                    # 责任人
    handler_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # 登记人
    created_at = db.Column(db.DateTime, default=datetime.now)

    instrument = db.relationship("Instrument")
    handler = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument.name if self.instrument else "",
            "instrument_code": self.instrument.code if self.instrument else "",
            "quantity": self.quantity,
            "loss_time": self.loss_time.strftime("%Y-%m-%d %H:%M") if self.loss_time else None,
            "reason": self.reason,
            "responsible": self.responsible,
            "handler_name": self.handler.name if self.handler else "",
        }


class PurchaseRequest(db.Model):
    """采购申报表"""
    __tablename__ = "purchase_requests"
    id = db.Column(db.Integer, primary_key=True)
    instrument_name = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=1)
    budget = db.Column(db.Float, default=0)                   # 预算（元）
    reason = db.Column(db.Text)                               # 申请理由
    status = db.Column(db.String(20), default="草稿")     # 草稿/已提交/已审批/已驳回/已采购
    applicant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    review_comment = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.now)

    applicant = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "instrument_name": self.instrument_name,
            "model": self.model,
            "quantity": self.quantity,
            "budget": self.budget,
            "reason": self.reason,
            "status": self.status,
            "applicant_id": self.applicant_id,
            "applicant_name": self.applicant.name if self.applicant else "",
            "review_comment": self.review_comment,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class ExperimentReport(db.Model):
    """实验报告表（含实验使用登记与过程记录）"""
    __tablename__ = "experiment_reports"
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"))
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    experiment_name = db.Column(db.String(200), nullable=False)
    actual_time = db.Column(db.DateTime)                      # 实际使用时间
    class_name = db.Column(db.String(100))                    # 参与班级
    group_info = db.Column(db.String(300))                    # 分组情况
    instruments_used = db.Column(db.String(500))              # 使用仪器
    content = db.Column(db.Text)                              # 实验内容/过程
    result = db.Column(db.Text)                               # 实验结果
    exception = db.Column(db.Text)                            # 异常情况
    attachment = db.Column(db.String(300))                    # 附件文件名
    created_at = db.Column(db.DateTime, default=datetime.now)

    teacher = db.relationship("User")
    reservation = db.relationship("Reservation")

    def to_dict(self):
        return {
            "id": self.id,
            "reservation_id": self.reservation_id,
            "teacher_id": self.teacher_id,
            "teacher_name": self.teacher.name if self.teacher else "",
            "experiment_name": self.experiment_name,
            "actual_time": self.actual_time.strftime("%Y-%m-%d %H:%M") if self.actual_time else None,
            "class_name": self.class_name,
            "group_info": self.group_info,
            "instruments_used": self.instruments_used,
            "content": self.content,
            "result": self.result,
            "exception": self.exception,
            "attachment": self.attachment,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class Notice(db.Model):
    """实验通知单表"""
    __tablename__ = "notices"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)         # 实验名称
    subject = db.Column(db.String(50))                        # 科目
    classes = db.Column(db.String(200))                       # 参与班级（多个，分隔）
    teacher_name = db.Column(db.String(50))                   # 任教教师
    lab_name = db.Column(db.String(100))                      # 地点
    experiment_time = db.Column(db.String(50))                # 实验时间（自选）
    instruments = db.Column(db.String(500))                   # 实验仪器、用品
    content = db.Column(db.Text)                              # 实验内容/注意事项
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.now)

    sender = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "subject": self.subject,
            "classes": self.classes,
            "teacher_name": self.teacher_name,
            "lab_name": self.lab_name,
            "experiment_time": self.experiment_time,
            "instruments": self.instruments,
            "content": self.content,
            "sender_name": self.sender.name if self.sender else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class OperationLog(db.Model):
    """操作日志表：记录敏感操作（设计文档 7.3）"""
    __tablename__ = "operation_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "user_name": self.user.name if self.user else "",
            "action": self.action,
            "detail": self.detail,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class InstrumentCatalog(db.Model):
    """初中教学仪器配备目录（预留配备标准，供采购/对照参考）"""
    __tablename__ = "instrument_catalog"
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), index=True)    # 学科（如 初中生物）
    category = db.Column(db.String(200))              # 器材类型/学习主题
    old_code = db.Column(db.String(50))               # 老编码
    code = db.Column(db.String(50), index=True)       # 分类代码
    name = db.Column(db.String(200), nullable=False)  # 器材名称
    spec = db.Column(db.Text)                         # 规格、品名、教学性能要求
    unit = db.Column(db.String(20))                   # 单位
    quantity = db.Column(db.Integer)                  # 配备数量
    price = db.Column(db.Float)                       # 单价（元）
    requirement = db.Column(db.String(20))            # 配备要求（必配/选配）
    remark = db.Column(db.Text)                       # 备注
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "subject": self.subject, "category": self.category,
            "old_code": self.old_code, "code": self.code, "name": self.name,
            "spec": self.spec, "unit": self.unit, "quantity": self.quantity,
            "price": self.price, "requirement": self.requirement, "remark": self.remark,
        }
