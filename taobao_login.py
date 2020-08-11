# --*--coding: utf-8 --*--
import json
import re
import os
import requests
from loguru import logger

session = requests.Session()
cookie_path = 'taobao_cookies.txt'
logger.add("file_cookie.log")


class UsernameLogin(object):
    def __init__(self, loginId, umidToken, ua, password2):
        self.loginId = loginId
        self.umidToken = umidToken
        self.ua = ua
        self.password2 = password2
        self.timeout = 3
        self.user_check_url = 'https://login.taobao.com/newlogin/account/check.do?appName=taobao&fromSite=0'
        self.verify_password_url = "https://login.taobao.com/newlogin/login.do?appName=taobao&fromSite=0"
        self.vst_url = 'https://login.taobao.com/member/vst.htm?st={}'
        # 淘宝个人 主页
        self.my_taobao_url = 'http://i.taobao.com/my_taobao.htm'

    def _user_check(self):
        data = {
            'loginId': self.loginId,
            'ua': self.ua
        }
        try:
            res = session.post(self.user_check_url, data=data, timeout=self.timeout)
            res.raise_for_status()
        except Exception as e:
            logger.warning("检测是否需要验证码")
        check_reponse_data = res.json()['content']['data']
        needcode = False
        # 判断是否需要验证码，短时间多次密码错误可能会出现
        if 'isCheckCodeShowed' in check_reponse_data:
            needcode = True
        return needcode

    @property
    def _verify_password(self):
        # y验证用户名和密码，并返回成功的st码
        verify_password_headers = {
            'Origin': 'https://login.taobao.com',
            'content-type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://login.taobao.com/member/login.jhtml?spm=a21bo.2017.754894437.1.5af911d9HjW9WC&f=top&redirectURL=https%3A%2F%2Fwww.taobao.com%2F',
        }

        verify_password_data = {
            'ua': self.ua,
            'loginId': self.loginId,
            'password2': self.password2,
            'umidToken': self.umidToken,
            'appEntrance': 'taobao_pc',
            'isMobile': 'false',
            'returnUrl': 'https://www.taobao.com/',
            'navPlatform': 'MacIntel',
        }
        try:
            response = session.post(self.verify_password_url, data=verify_password_data,
                                    headers=verify_password_headers, timeout=self.timeout)
            response.raise_for_status()
            print(response.json())
        except Exception as e:
            logger.warning('验证用户名和密码失败，原因：%s' % e)

        # 提取申请的st码

        apply_st_url_match = response.json()['content']['data']['asyncUrls'][0]
        # 存在则返回
        if apply_st_url_match:
            logger.info(f'验证用户名和密码成功，st码的申请地址为{apply_st_url_match}')
            return apply_st_url_match
        else:
            logger.info('验证用户名或密码失败')

    def apply_st(self):

        apply_st_url = self._verify_password
        try:
            response = session.get(apply_st_url)
            response.raise_for_status()

        except Exception as e:
            logger.info('获取st码失败')
        # st_match = re.search(r'"data":{"st":"(.*?)"}', response.text)
        st_match = re.search(r'"data":{"st":"(.*?)"}', response.text).group(1)
        if st_match:
            logger.info('st申请成功，嘻嘻嘻')
            return st_match
        else:
            logger.info('st申请失败，重新来')

    def login(self):
        # 使用st码登录淘宝
        if self._load_cookie():
            return True
        self._user_check()
        st = self.apply_st()
        headers = {
            'Host': 'login.taobao.com',
            'Connection': 'Keep-Alive',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        try:
            response = session.get(self.vst_url.format(st), headers=headers)
            response.raise_for_status()
        except Exception as e:
            logger.info('st码登录失败，原因：')
        my_taobao_match = re.search(r'top.location.href = "(.*?)"', response.text)
        if my_taobao_match:
            print('登录淘宝成功，跳转链接：{}'.format(my_taobao_match.group(1)))
            self.my_taobao_url = my_taobao_match.group(1)
            self._serialization_cookies()
            return True
        else:
            raise RuntimeError('登录失败！response：{}'.format(response.text))

    def get_taobao_nick_name(self):
        """
        获取淘宝昵称
        :return: 淘宝昵称
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
        }
        try:
            response = session.get(self.my_taobao_url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            print('获取淘宝主页请求失败！原因：')
            raise e
        # 提取淘宝昵称
        nick_name_match = re.search(r'<input id="mtb-nickname" type="hidden" value="(.*?)"/>', response.text)
        if nick_name_match:
            print('登录淘宝成功，你的用户名是：{}'.format(nick_name_match.group(1)))
            return nick_name_match.group(1)
        else:
            raise RuntimeError('获取淘宝昵称失败！response：{}'.format(response.text))

    def _load_cookie(self):
        # 判断cookies序列化文件是否存在
        if not os.path.exists(cookie_path):
            return False
        session.cookies = self._deserialization_cookies()
        try:
            self.get_taobao_nick_name()
        except Exception as e:
            os.remove(cookie_path)
            print('cookies过期，删除cookies文件！')
            return False
        print('加载淘宝cookies登录成功!!!')
        return True

    def _deserialization_cookies(self):
        with open(cookie_path, 'r', encoding='utf-8') as f:
            cookie_dict = json.load(f)
            cookies = requests.utils.cookiejar_from_dict(cookie_dict)
            return cookies

    def _serialization_cookies(self):

        cookies_dict = requests.utils.dict_from_cookiejar(session.cookies)
        with open(cookie_path, 'w+', encoding='utf-8') as file:
            json.dump(cookies_dict, file)
            logger.info('保存淘宝cookies文件成功')


if __name__ == '__main__':
    loginId = '13213857061'
    # 改版后增加的参数，后面考虑解密这个参数
    umidToken = 'c2b66b94be9d689886debc2fb40da02b66a81cd9',
    # 淘宝重要参数，从浏览器或抓包工具中复制，可重复使用
    ua = '134#QY74JgXwXGfYnkGRT6FPeX0D3QROwKO9sE/w4/PLrymcOUnrInq/EdfZ5wpMHX9QHVK7KJzR4g9f2clsxVUNtP81F9YZBj5i3VhSvFXimJowqqX3IkuU+4qAqVtu12nxzsefqc77rJja3X4qosro+dg+qRueTtwtXHpKqHKAjXrEqTpqqkPJ+242IghUgJGJJZY7/lCzS9WrYIokk37NRzp9Vj31EST1vgDe+w2BS6vo5DhqtFjzrRkPfDk+mXBC2f5OgnhMphe9o66rbg1qMkMXrs3cqNMVVJEv0rT6f0e5yTpO0Odr8WC/wulNRpJfadELuczAXTeDZ0j4tbYYhoBqKLpV9dedasIMZBCWEkLOgfxA85gWIRQVYEagBJPvIzGAmRz2AGphyQf8hm/O3aqdbdBbatmFSM3MeBsWH9ku8QVdsduJbC/tZfve+bJnxmApDQ2JPc31d98cLm7/eHCuAeBJVOW9rTbvdxyDBvSoaNj6C46+q/NXqx9G9/WpgYKm74V0zu9SunGhpS95Vf644OzdgX47HrBozZnej+ybVyTwXnS3HeF0l7e9T5X8lGxu17Otggzgdb+++EFMDlaK7TYfKpvDK65VlKafMTa7rhWLcEbzovhyDjBRICFqTPy3T8anEnRgg1kr0UNW9kCQiakYQ/n2E7LYgclHLlYFFb89OVO1Snup3vEpMcKtPAf6zXFgF/3PMMlctC5wodYHd7UNjIyrl03V/PG4Bp2IPWg11QdumV1e1bL1gbEC38DK4tdVlli+UqazWDCKNRqAjMRXzQCG5pNW/D+/HfZiwO+zFiifSkJ0HyTdY6AgPh0JxSLCScDQmcSGiUagB4uGGN7UVt6zzSd62MO+jnz5Q+XiJEXSYQ7BDcA6ideHDoyhcWkRgT9JWq/aoSa0qsDQksXuyERg+g1xxOIogObvY8XuGHa3FE25QPs1gnFn+pLhNBQ3cvxlbPFcE6d0IA2kZiCE0AeWXcKJ20Fy4HBSbKjOEh4A7I8RAT1nIznCTs9a1i44W53vDo1zR9itZ0/+73Rq7suXZKYPhNv6bBAOhk0b83zfNSAwsL+ZNKt0Xjavnmw+NOJnI5rNxDxyUZcJXvsvM44mCjIcD76w'
    # 加密后的密码，从浏览器或抓包工具中复制，可重复使用
    password2 = '59fd1c4631fe398245691026b062d422c91d7e688f40492abce4b996aa43f5f367270d845c0f52d6500da96d57531f2ca72f5eba165d4e79ada7224c2045f2acc1d9ed57f03e508a69a04a58beabc4b1e9922af8256b3abd2d639e5e81b259beb6147355c469816040d90fd9c96ef80ac6bb7652da7b716bb9b9285a89064cc3'

    ul = UsernameLogin(loginId, umidToken, ua, password2)
    ul.login()
    ul.get_taobao_nick_name()
