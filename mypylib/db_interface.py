import logging
import random
import string
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Union

# from cachetools import TTLCache
from faker import Faker
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
import pytz

from mypylib.utils import combine_date_and_time_to_utc

from .constants import FAKE_EMAIL_DOMAIN
from .db_model import (
    LearningTime,
    Payment,
    PaymentStatus,
    PurchaseType,
    TokenUsageRecord,
    User,
)

# 创建或获取logger对象
logger = logging.getLogger("streamlit")


PRICES = {
    PurchaseType.ANNUAL: 6570,
    PurchaseType.QUARTERLY: 1890,
    PurchaseType.MONTHLY: 720,
    PurchaseType.WEEKLY: 210,
    PurchaseType.DAILY: 30,
}


CACHE_TRIGGER_SIZE = 100
MAX_TIME_INTERVAL = 10 * 60  # 10 分钟


class DbInterface:
    def __init__(self, firestore_client):
        self.faker = Faker("zh_CN")
        self.db = firestore_client
        self.cache = {
            "user_info": {},
            "personal_vocabulary": {
                "words": set(),
                "last_commit_time": time.time(),
                "to_add": [],
                "to_delete": [],
            },
        }
        self.start_timer()

    def start_timer(self):
        self.timer = threading.Timer(600, self.save_cache)
        self.timer.start()

    def cache_user_login_info(self, user, session_id):
        phone_number = user.phone_number
        self.cache["user_info"] = {
            "is_logged_in": True,
            "phone_number": phone_number,
            "display_name": user.display_name,
            "email": user.email,
            "user_role": user.user_role,
            "timezone": user.timezone,
            "session_id": session_id,
        }

    # region 用户管理

    def get_user(self, return_object=True):
        phone_number = self.cache.get("user_info", {}).get("phone_number", "")
        if not phone_number:
            return None
        doc_ref = self.db.collection("users").document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            user_data = doc.to_dict()
            user_data["phone_number"] = phone_number  # 添加手机号码
            if return_object:
                return User.from_doc(user_data)
            else:
                return user_data
        else:
            return None

    def update_user(self, update_fields: dict):
        phone_number = self.cache["user_info"]["phone_number"]
        doc_ref = self.db.collection("users").document(phone_number)
        try:
            del update_fields["phone_number"]  # 删除手机号码
        except KeyError:
            pass
        doc_ref.update(update_fields)

    def register_user(self, user: User):
        phone_number = user.phone_number
        doc_ref = self.db.collection("users").document(phone_number)
        # 为用户密码加密
        user.hash_password()
        user_data = user.model_dump()
        try:
            del user_data["phone_number"]  # 删除手机号码
        except KeyError:
            pass
        doc_ref.set(user_data)

    # endregion

    # region 登录管理

    def create_login_event(self, phone_number):
        # 创建一个登录事件
        session_id = str(uuid.uuid4())
        login_events_ref = self.db.collection("login_events")
        login_event_doc_ref = login_events_ref.document(session_id)
        login_event_doc_ref.set(
            {
                "phone_number": phone_number,
                "login_time": datetime.now(timezone.utc),
                "logout_time": None,
            }
        )
        return session_id

    def is_logged_in(self):
        return self.cache.get("user_info", {}).get("is_logged_in", False)

    def login(self, phone_number, password):
        # 在缓存中查询是否已经正常登录
        if self.cache.get("user_info", {}).get("is_logged_in", False):
            return {"status": "warning", "message": "您已登录"}
        # 检查用户的凭据
        users_ref = self.db.collection("users")
        user_doc_ref = users_ref.document(phone_number)
        user_doc = user_doc_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_data["phone_number"] = phone_number  # 添加手机号码
            user = User.from_doc(user_data)
            # 验证密码
            if user.check_password(password):
                # 验证服务活动状态
                payments = (
                    self.db.collection("payments")
                    .where(filter=FieldFilter("phone_number", "==", phone_number))
                    .stream()
                )
                now = datetime.now(timezone.utc)
                is_expired = True
                for payment in payments:
                    payment_dict = payment.to_dict()
                    expiry_time = payment_dict["expiry_time"].replace(
                        tzinfo=timezone.utc
                    )
                    if payment_dict["is_approved"] and expiry_time > now:
                        is_expired = False
                        break
                if not is_expired or (user.user_role in ("管理员", "超级成员")):
                    session_id = self.create_login_event(phone_number)
                    # 如果密码正确，将用户的登录状态存储到缓存中
                    self.cache_user_login_info(user, session_id)
                    return {
                        "status": "success",
                        "message": f"嗨！{user.display_name}，又见面了。",
                    }
                else:
                    # TODO：单列 过期状态 以及 付费状态 st.switch_page("付费.py")
                    return {
                        "status": "warning",
                        "message": "您尚未付费订阅或者服务账号已过期，请付费订阅。",
                    }
            else:
                return {
                    "status": "warning",
                    "message": "密码错误，请重新输入",
                }
        else:
            return {
                "status": "error",
                "message": f"不存在与手机号码 {phone_number} 相关联的用户",
            }

    def logout(self):
        phone_number = self.cache["user_info"]["phone_number"]
        # 从缓存中删除用户的登录状态
        self.cache["user_info"] = {}

        login_events_ref = self.db.collection("login_events")
        login_events = (
            login_events_ref.where(
                filter=FieldFilter("phone_number", "==", phone_number)
            )
            .where(filter=FieldFilter("logout_time", "==", None))
            .stream()
        )

        for login_event in login_events:
            login_event.reference.update({"logout_time": datetime.now(tz=timezone.utc)})

        return "Logout successful"

    # endregion

    # region 个人词库管理

    def _commit_personal_vocabulary_to_db(self):
        """
        将缓存中的个人词库提交到数据库。
        """
        phone_number = self.cache["user_info"]["phone_number"]
        # 获取用户文档的引用
        user_doc_ref = self.db.collection("users").document(phone_number)
        # 从数据库中读取个人词库
        personal_vocabulary_in_db = (
            user_doc_ref.get().to_dict().get("personal_vocabulary", [])
        )
        # 计算需要添加和删除的单词
        words_to_add = list(
            set(self.cache["personal_vocabulary"]["words"])
            - set(personal_vocabulary_in_db)
        )
        words_to_delete = list(
            set(personal_vocabulary_in_db)
            - set(self.cache["personal_vocabulary"]["words"])
        )
        # 使用 arrayUnion 方法添加单词到数据库中的个人词库
        if words_to_add:
            user_doc_ref.update(
                {"personal_vocabulary": firestore.ArrayUnion(words_to_add)}
            )
        # 使用 arrayRemove 方法从数据库中的个人词库中移除单词
        if words_to_delete:
            user_doc_ref.update(
                {"personal_vocabulary": firestore.ArrayRemove(words_to_delete)}
            )
        # 更新最后提交时间
        self.cache["personal_vocabulary"]["last_commit_time"] = time.time()
        # 清理 to_add 和 to_delete 列表
        self.cache["personal_vocabulary"]["to_add"] = []
        self.cache["personal_vocabulary"]["to_delete"] = []

    def find_personal_dictionary(self):
        # 如果缓存中存在个人词库，直接返回
        if (
            "personal_vocabulary" in self.cache
            and self.cache["personal_vocabulary"]["words"]
        ):
            return list(self.cache["personal_vocabulary"]["words"])

        phone_number = self.cache["user_info"]["phone_number"]
        # 获取用户文档的引用
        user_doc_ref = self.db.collection("users").document(phone_number)
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            # 从数据库中读取个人词库，并缓存
            self.cache["personal_vocabulary"] = {
                "words": set(user_data.get("personal_vocabulary", [])),
                "last_commit_time": time.time(),
                "to_add": [],
                "to_delete": [],
            }
        else:
            self.cache["personal_vocabulary"] = {
                "words": set(),
                "last_commit_time": time.time(),
                "to_add": [],
                "to_delete": [],
            }

        return list(self.cache["personal_vocabulary"]["words"])

    def add_words_to_personal_dictionary(self, word: Union[str, List[str]]):
        """
        将单词添加到缓存中的个人词库。
        """
        if isinstance(word, list):
            self.cache["personal_vocabulary"]["words"].update(word)
            self.cache["personal_vocabulary"]["to_add"].extend(word)
        else:
            self.cache["personal_vocabulary"]["words"].add(word)
            self.cache["personal_vocabulary"]["to_add"].append(word)

        if (
            len(self.cache["personal_vocabulary"]["to_add"])
            + len(self.cache["personal_vocabulary"]["to_delete"])
            >= CACHE_TRIGGER_SIZE
            or time.time() - self.cache["personal_vocabulary"]["last_commit_time"]
            >= MAX_TIME_INTERVAL
        ):
            self._commit_personal_vocabulary_to_db()

    def remove_words_from_personal_dictionary(self, word: Union[str, List[str]]):
        """
        从缓存中的个人词库中移除单词。
        """
        if isinstance(word, list):
            self.cache["personal_vocabulary"]["words"].difference_update(word)
            self.cache["personal_vocabulary"]["to_delete"].extend(word)
        else:
            self.cache["personal_vocabulary"]["words"].discard(word)
            self.cache["personal_vocabulary"]["to_delete"].append(word)

        if (
            len(self.cache["personal_vocabulary"]["to_add"])
            + len(self.cache["personal_vocabulary"]["to_delete"])
            >= CACHE_TRIGGER_SIZE
            or time.time() - self.cache["personal_vocabulary"]["last_commit_time"]
            >= MAX_TIME_INTERVAL
        ):
            self._commit_personal_vocabulary_to_db()

    # endregion

    # region token

    def get_token_count(self):
        phone_number = self.cache["user_info"]["phone_number"]
        # 获取用户文档的引用
        user_doc_ref = self.db.collection("users").document(phone_number)
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return user_data.get("total_tokens", 0)
        else:
            return 0

    def add_token_record(self, token_type, used_token_count):
        phone_number = self.cache["user_info"]["phone_number"]
        used_token = TokenUsageRecord(
            token_type=token_type,
            used_token_count=used_token_count,
            used_at=datetime.now(tz=timezone.utc),
            phone_number=phone_number,
        )

        # 添加 token 记录到 'token_records' 集合
        token_records_ref = self.db.collection("token_records")
        token_records_ref.document().set(used_token.model_dump())

        # 更新用户的 'total_tokens' 属性
        user_doc_ref = self.db.collection("users").document(phone_number)
        user_doc_ref.update({"total_tokens": firestore.Increment(used_token_count)})

    # endregion

    # region 支付管理

    def get_last_active_payment(self):
        payments_ref = self.db.collection("payments")
        query = (
            payments_ref.where(
                filter=FieldFilter(
                    "phone_number", "==", self.cache["user_info"]["phone_number"]
                )
            )
            .where(filter=FieldFilter("status", "==", PaymentStatus.IN_SERVICE))
            .order_by("payment_time", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = query.get()
        if docs:
            return {"order_id": docs[0].id, **docs[0].to_dict()}
        else:
            return {}

    def query_payments(self, query_dict: dict):
        # 检查所有的值是否有效
        invalid_keys = [key for key, value in query_dict.items() if value is None]
        if invalid_keys:
            raise ValueError(
                f"在查询支付记录时传入的键值对参数 {', '.join(invalid_keys)} 无效。"
            )

        query = self.db.collection("payments")
        for key in [
            "phone_number",
            "payment_id",
            "purchase_type",
            "sales_representative",
            "status",
            "is_approved",
        ]:
            if key in query_dict:
                query = query.where(filter=FieldFilter(key, "==", query_dict[key]))

        if "order_id" in query_dict:
            doc_ref = self.db.collection("payments").document(query_dict["order_id"])
            doc = doc_ref.get()
            if doc.exists:
                return [doc]
            else:
                return []

        for key in [
            "start_payment_time",
            "end_payment_time",
            "start_expiry_time",
            "end_expiry_time",
        ]:
            if key in query_dict:
                if "start" in key:
                    query = query.where(
                        filter=FieldFilter(
                            key.replace("start_", ""), ">=", query_dict[key]
                        )
                    )
                else:
                    query = query.where(
                        filter=FieldFilter(
                            key.replace("end_", ""), "<=", query_dict[key]
                        )
                    )
        results = query.stream()
        if "remark" in query_dict:
            results = [
                doc
                for doc in results
                if query_dict["remark"] in doc.to_dict().get("remark", "")
            ]
        if "payment_method" in query_dict:
            results = [
                doc
                for doc in results
                if query_dict["payment_method"]
                in doc.to_dict().get("payment_method", "")
            ]
        return results

    def update_payment(self, order_id, update_fields: dict):
        payments_ref = self.db.collection("payments")
        payment_doc_ref = payments_ref.document(order_id)
        payment_doc_ref.update(update_fields)

    def delete_payment(self, order_id):
        payments_ref = self.db.collection("payments")
        payment_doc_ref = payments_ref.document(order_id)
        payment_doc_ref.delete()

    def enable_service(self, payment: Payment):
        # 查询用户的最后一个订阅记录
        payments_ref = self.db.collection("payments")
        payments_query = (
            payments_ref.where(
                filter=FieldFilter("phone_number", "==", payment.phone_number)
            )
            .where(filter=FieldFilter("status", "==", PaymentStatus.IN_SERVICE))
            .order_by("expiry_time", direction=firestore.Query.DESCENDING)
        )
        last_subscription_docs = payments_query.stream()
        last_subscription = next(last_subscription_docs, None)

        # 创建一个包含时区信息的 datetime 对象
        now = datetime.now(timezone.utc)
        base_time = now
        # 如果存在未过期的订阅，以其到期时间为基准
        if last_subscription is not None:
            last_subscription = last_subscription.to_dict()
            # 将字符串转换为 datetime 对象
            last_subscription_expiry_time = last_subscription["expiry_time"].replace(
                tzinfo=timezone.utc
            )
            if last_subscription_expiry_time > now:
                base_time = last_subscription_expiry_time

        # 将字符串转换为 PurchaseType 枚举
        expiry_time = base_time + self.calculate_expiry(payment.purchase_type)  # type: ignore

        # 更新支付记录对象的状态和到期时间
        payment.is_approved = True
        payment.expiry_time = expiry_time
        payment.status = PaymentStatus.IN_SERVICE

    def calculate_expiry(self, purchase_type: PurchaseType):
        if purchase_type == PurchaseType.DAILY:
            return timedelta(days=1)
        elif purchase_type == PurchaseType.WEEKLY:
            return timedelta(days=7)
        elif purchase_type == PurchaseType.MONTHLY:
            return timedelta(days=30)
        elif purchase_type == PurchaseType.QUARTERLY:
            return timedelta(days=90)
        elif purchase_type == PurchaseType.ANNUAL:
            return timedelta(days=365)
        else:
            return timedelta(days=0)

    def add_payment(self, payment: Payment):
        phone_number = payment.phone_number
        users_ref = self.db.collection("users")
        user_doc_ref = users_ref.document(phone_number)
        user_doc = user_doc_ref.get()

        if not user_doc.exists:
            # 如果用户不存在，则创建一个新用户
            new_user = User(
                display_name=self.faker.user_name(),
                email=f"{phone_number}@{FAKE_EMAIL_DOMAIN}",
                phone_number=phone_number,
                password=phone_number,
                timezone="Asia/Shanghai",
                country="中国",
                province="上海",
                registration_time=datetime.now(timezone.utc),
                memo=f"订单号：{payment.order_id}",
            )  # type: ignore
            self.register_user(new_user)

        if payment.is_approved or (payment.receivable == payment.payment_amount):
            # 更新到期时间
            self.enable_service(payment)
        # 添加支付记录
        payments_ref = self.db.collection("payments")
        payment_data = payment.model_dump()
        # 从数据中删除 order_id
        del payment_data["order_id"]
        payment_doc_ref = payments_ref.document(payment.order_id)
        payment_doc_ref.set(payment_data, merge=True)

    # endregion

    # region 会话管理

    def generate_verification_code(self, phone_number: str):
        # 生成一个6位数的验证码
        verification_code = "".join(random.choice(string.digits) for _ in range(6))
        # 获取用户文档的引用
        user_doc_ref = self.db.collection("users").document(phone_number)
        # 更新用户的文档，添加验证码和生成时间
        user_doc_ref.update(
            {
                "verification_code": verification_code,
                "verification_code_time": datetime.now(timezone.utc),
            }
        )
        return verification_code

    def login_with_verification_code(self, phone_number: str, verification_code: str):
        # 在缓存中查询是否已经正常登录
        if self.cache.get("user_info", {}).get("is_logged_in", False):
            return {"status": "warning", "message": "您已登录"}

        # 获取用户文档的引用
        user_doc_ref = self.db.collection("users").document(phone_number)
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_data["phone_number"] = phone_number  # 添加手机号码
            user = User.from_doc(user_data)
            # 检查验证码是否正确
            if user_data.get("verification_code") == verification_code:
                # 检查验证码是否在有效期内
                if user_data.get("verification_code_time") + timedelta(
                    minutes=30
                ) > datetime.now(timezone.utc):
                    session_id = self.create_login_event(phone_number)
                    # 如果验证码正确且在有效期内，将用户的登录状态存储到缓存中
                    self.cache_user_login_info(user, session_id)
                    return {
                        "display_name": user.display_name,
                        "session_id": session_id,
                        "is_logged_in": True,
                        "user_role": user.user_role,
                        "timezone": user.timezone,
                        "message": f"嗨！{user.display_name}，又见面了。",
                    }
                else:
                    return {
                        "status": "error",
                        "message": "验证码已过期",
                    }
            else:
                return {
                    "status": "error",
                    "message": "验证码错误",
                }
        else:
            return {
                "status": "error",
                "message": f"不存在与手机号码 {phone_number} 相关联的用户",
            }

    def get_active_sessions(self):
        phone_number = self.cache.get("user_info", {}).get("phone_number", "")
        if not phone_number:
            return []
        login_events_ref = self.db.collection("login_events")
        login_events_query = (
            login_events_ref.where(
                filter=FieldFilter("phone_number", "==", phone_number)
            )
            .where(filter=FieldFilter("logout_time", "==", None))
            .order_by("login_time", direction=firestore.Query.ASCENDING)
        )
        login_events_docs = login_events_query.stream()
        dicts = [{"session_id": doc.id, **doc.to_dict()} for doc in login_events_docs]
        if len(dicts) > 1:
            return dicts[:-1]  # 返回除最后一个登录事件外的所有未退出的登录事件
        return []

    def force_logout_session(self, phone_number: str, session_id: str):
        login_events_ref = self.db.collection("login_events")
        login_event_doc_ref = login_events_ref.document(session_id)
        login_event_doc = login_event_doc_ref.get()
        if (
            login_event_doc.exists
            and login_event_doc.to_dict()["phone_number"] == phone_number
        ):
            login_event_doc_ref.update({"logout_time": datetime.now(timezone.utc)})

    # endregion

    # region 单词管理

    def find_word(self, word):
        # 将单词中的 "/" 字符替换为 " or "
        word = word.replace("/", " or ")

        # 获取指定 ID 的文档
        doc = self.db.collection("words").document(word).get()

        # 如果文档存在，将其转换为字典，否则返回一个空字典
        return doc.to_dict() if doc.exists else {}

    def find_docs_with_empty_level(self):
        mini_dict_ref = self.db.collection("mini_dict")
        docs = mini_dict_ref.where(filter=FieldFilter("level", "==", None)).stream()
        return [doc.id for doc in docs]

    def update_level(self, word_cefr):
        word, level = list(word_cefr.items())[0]
        doc_ref = self.db.collection("mini_dict").document(word)
        doc = doc_ref.get()
        doc_dict = doc.to_dict()
        if "level" in doc_dict and doc_dict["level"] is None:
            if level is None:
                level = "未分级"
            doc_ref.update({"level": level})

    def batch_update_levels(self, words_cefr):
        words = list(words_cefr.keys())
        for i in range(0, len(words), 500):
            batch = self.db.batch()
            words_batch = words[i : i + 500]
            for word in words_batch:
                doc_ref = self.db.collection("mini_dict").document(word)
                doc = doc_ref.get()
                doc_dict = doc.to_dict()
                if (
                    "level" in doc_dict
                    and doc_dict["level"] is None
                    and words_cefr[word] is not None
                ):
                    batch.update(doc_ref, {"level": words_cefr[word]})
            batch.commit()

    def find_docs_with_category(self, category):
        # 获取 mini_dict 集合的引用
        mini_dict_ref = self.db.collection("mini_dict")

        field = "categories"
        # 查询所有 categories 字段包含指定类别的文档
        docs = mini_dict_ref.where(
            filter=FieldFilter(field, "array_contains", category)
        ).stream()
        # 获取所有文档的数据
        doc_data = [
            {
                "单词": doc.id,
                "CEFR最低分级": doc_dict.get("level", ""),
                "翻译": doc_dict.get("translation", ""),
            }
            for doc in docs
            for doc_dict in [doc.to_dict()]
        ]
        return doc_data

    def find_docs_with_empty_image_urls(self):
        # 获取 mini_dict 集合的引用
        mini_dict_ref = self.db.collection("mini_dict")

        # 初始化一个空列表来存储 image_urls 为空的文档名称
        docs_with_empty_image_urls = []

        # 遍历 mini_dict 集合中的所有文档
        for doc in mini_dict_ref.stream():
            # 将 DocumentSnapshot 对象转换为字典
            doc_dict = doc.to_dict()

            # 检查 image_urls 字段是否不存在或者为空
            if "image_urls" not in doc_dict or not doc_dict["image_urls"]:
                # 如果 image_urls 字段不存在或者为空，将文档名称添加到列表中
                docs_with_empty_image_urls.append(doc.id)

        # 返回 image_urls 为空的文档名称列表
        return docs_with_empty_image_urls

    def word_has_image_urls(self, word: str) -> bool:
        # 获取文档
        doc = self.db.collection("mini_dict").document(word).get()

        # 如果文档不存在，返回 False
        if not doc.exists:
            return False

        # 将 DocumentSnapshot 对象转换为字典
        doc_dict = doc.to_dict()

        # 检查 image_urls 字段是否存在且不为空
        return "image_urls" in doc_dict and bool(doc_dict["image_urls"])

    def update_image_urls(self, word: str, urls: list):
        # 将单词中的 "/" 字符替换为 " or "
        word = word.replace("/", " or ")

        # 更新或添加 image_urls 字段
        self.db.collection("mini_dict").document(word).set(
            {"image_urls": urls}, merge=True
        )

    def get_image_indices(self, doc_name):
        # 获取 mini_dict 集合中的文档引用
        doc_ref = self.db.collection("mini_dict").document(doc_name)

        # 获取文档的数据
        doc = doc_ref.get()

        # 如果文档存在并且包含 image_indices 字段，返回该字段的值
        # 否则，返回一个空列表
        if doc.exists and "image_indices" in doc.to_dict():
            return doc.to_dict()["image_indices"]
        else:
            return []

    def update_image_indices(self, word: str, indices: list):
        # 将单词中的 "/" 字符替换为 " or "
        word = word.replace("/", " or ")

        # 更新或添加 image_urls 字段
        self.db.collection("mini_dict").document(word).set(
            {"image_indices": indices}, merge=True
        )

    def word_has_image_indices(self, word: str) -> bool:
        # 获取文档
        doc = self.db.collection("mini_dict").document(word).get()

        # 如果文档不存在，返回 False
        if not doc.exists:
            return False

        # 将 DocumentSnapshot 对象转换为字典
        doc_dict = doc.to_dict()

        return "image_indices" in doc_dict and bool(doc_dict["image_indices"])

    def find_docs_without_image_indices(self, doc_names):
        # 获取 "words" 集合
        collection = self.db.collection("mini_dict")

        # 存储没有 "image_indices" 字段的文档的名称
        doc_names_without_image_indices = []

        # 遍历所有文档名称
        for doc_name in doc_names:
            # 获取文档
            doc = collection.document(doc_name).get()

            # 将 DocumentSnapshot 对象转换为字典
            doc_dict = doc.to_dict()

            # 检查 "image_indices" 字段是否存在
            if "image_indices" not in doc_dict:
                # 如果 "image_indices" 字段不存在，将文档的名称添加到列表中
                doc_names_without_image_indices.append(doc_name)

        return doc_names_without_image_indices

    # endregion

    # region 学习记录

    def add_record_to_cache(self, learning_time):
        # 定义缓存
        if "learning_time_cache" not in self.cache:
            self.cache["learning_time_cache"] = []
            self.cache["learning_time_last_save_time"] = time.time()

        # 检查新添加的 LearningTime 实例是否与缓存中的最后一个实例有相同的项目和内容
        if (
            len(self.cache["learning_time_cache"]) > 0
            and self.cache["learning_time_cache"][-1].project == learning_time.project
            and self.cache["learning_time_cache"][-1].content == learning_time.content
        ):
            # 如果是，将新实例的时长添加到最后一个实例的时长上
            self.cache["learning_time_cache"][-1].duration += learning_time.duration
        else:
            # 如果不是，将新实例添加到缓存中
            self.cache["learning_time_cache"].append(learning_time)

        # 如果缓存数量超过限制或者时间超过限制，将缓存中的 LearningTime 对象保存到数据库
        if (
            len(self.cache["learning_time_cache"]) > CACHE_TRIGGER_SIZE
            or time.time() - self.cache["learning_time_last_save_time"]
            > MAX_TIME_INTERVAL
        ):
            self.save_learning_time(self.cache["learning_time_cache"])
            self.cache["learning_time_cache"] = []
            self.cache["learning_time_last_save_time"] = time.time()

    def save_learning_time(self, records: List[LearningTime]):
        # 获取 "learning_records" 集合
        collection = self.db.collection("learning_time")

        # 创建一个 WriteBatch 对象
        batch = self.db.batch()

        # 添加记录
        for record in records:
            # 将 LearningRecord 对象转换为字典
            record_dict = record.model_dump()
            results_dict = {k: v for k, v in record_dict.items() if v is not None}
            # 只保存时长大于 0 的记录
            if results_dict.get("duration", 0) > 0:
                doc_ref = collection.document()
                batch.set(doc_ref, results_dict)

        # 提交批处理
        batch.commit()

    def save_daily_quiz_results(self, results: dict):
        # 获取 "daily_quiz_results" 集合
        collection = self.db.collection("daily_quiz_results")

        # 将结果字典转换为 Firestore 可接受的格式
        results_dict = {k: v for k, v in results.items() if v is not None}

        # 创建一个新的文档并设置其内容
        collection.document().set(results_dict)

    # endregion

    # region 使用及费用记录

    def list_usages_phone_number(self):
        """
        获取所有使用记录的电话号码列表。

        Returns:
            list: 包含所有电话号码的列表。
        """
        collection_ref = self.db.collection("usages")
        docs = collection_ref.get()
        phone_numbers = [doc.id for doc in docs]
        return phone_numbers

    def get_usage_records(self, phone_number, start_date=None, end_date=None):
        """
        根据电话号码获取使用记录。

        Args:
            phone_number (str): 要查询的电话号码，如果为 "ALL"，则查询所有记录。
            start_date (datetime.date, optional): 开始日期。默认为 None。
            end_date (datetime.date, optional): 结束日期。默认为 None。

        Returns:
            list: 包含所有匹配的使用记录的列表，每个记录是一个字典，包含 item_name, cost 和 timestamp 字段。
        """
        user_info = self.cache.get("user_info", {})
        timezone_str = user_info.get("timezone", "Asia/Shanghai")
        tz = pytz.timezone(timezone_str)
        collection_ref = self.db.collection("usages")
        usage_records = []

        start_timestamp = None
        end_timestamp = None

        if start_date is not None:
            start_datetime = combine_date_and_time_to_utc(
                start_date, timezone_str, True
            )
            start_timestamp = start_datetime.timestamp()

        if end_date is not None:
            end_datetime = combine_date_and_time_to_utc(end_date, timezone_str, False)
            end_timestamp = end_datetime.timestamp()

        if phone_number != "ALL":
            phone_numbers = [phone_number]
        else:
            # 获取所有文档的 ID
            phone_numbers = [doc.id for doc in collection_ref.stream()]

        for phone_number in phone_numbers:
            doc_ref = collection_ref.document(phone_number)
            doc = doc_ref.get()
            if doc.exists:
                usages = doc.to_dict().get("usages", [])
                for usage in usages:
                    timestamp = usage["timestamp"].timestamp()
                    if start_timestamp is not None and timestamp < start_timestamp:
                        continue
                    if end_timestamp is not None and timestamp > end_timestamp:
                        continue

                    timestamp_datetime = datetime.fromtimestamp(timestamp)
                    timestamp_in_timezone = timestamp_datetime.astimezone(tz)
                    usage_records.append(
                        {
                            "phone_number": phone_number,
                            "service_name": usage["service_name"],
                            "item_name": usage["item_name"],
                            "cost": usage["cost"],
                            "model": usage.get("model_name", ""),
                            "timestamp": timestamp_in_timezone,
                        }
                    )

        return usage_records

    def add_usage_to_cache(self, usage: dict):
        # 定义缓存
        if "usage_cache" not in self.cache:
            self.cache["usage_cache"] = []
            self.cache["usage_last_save_time"] = time.time()

        self.cache["usage_cache"].append(usage)

        # 如果缓存数量超过限制或者时间超过限制，将缓存中的 usage 对象保存到数据库
        if (
            len(self.cache["usage_cache"]) > CACHE_TRIGGER_SIZE
            or time.time() - self.cache["usage_last_save_time"] > MAX_TIME_INTERVAL
        ):
            self.save_usage(self.cache["usage_cache"])
            self.cache["usage_cache"] = []
            self.cache["usage_last_save_time"] = time.time()

    def save_usage(self, usage_list):
        if len(usage_list) == 0:
            return
        phone_number = self.cache["user_info"]["phone_number"]
        batch = self.db.batch()

        doc_ref = self.db.collection("usages").document(phone_number)
        batch.set(doc_ref, {"usages": firestore.ArrayUnion(usage_list)}, merge=True)

        batch.commit()

    def save_cache(self):
        if "usage_cache" in self.cache and self.cache["usage_cache"]:
            self.save_usage(self.cache["usage_cache"])
            self.cache["usage_cache"] = []
            self.cache["usage_last_save_time"] = time.time()
        self.start_timer()

    # endregion
