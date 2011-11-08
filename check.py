from BeautifulSoup import BeautifulSoup
from ConfigParser import ConfigParser
from urlparse import urlparse, urlunparse
import smtplib
from time import strptime
from datetime import datetime
from zope.testbrowser.browser import Browser


class Check(object):

    def __init__(self):
        config = ConfigParser()
        try:
            config.read('secret.cfg')
        except:
            raise Exception("You need a secret.cfg file")
        self.acc_user = config.get('account', 'user')
        self.acc_pass = config.get('account', 'pass')
        self.starturl = config.get('account', 'loginurl')
        self.reporturl = config.get('account', 'reporturl')
        self.mailhost = config.get('mail', 'mailhost')
        self.port = config.get('mail', 'port')
        self.mail_user = config.get('mail', 'user')
        self.mail_pass = config.get('mail', 'pass')
        self.from_ = config.get('mail', 'from')
        self.to = config.get('mail', 'to')
        self.urgent = int(config.get('config', 'urgent_after_n_days'))
        self.ignore = config.get('config', 'users_to_ignore').split(';')

    def __call__(self):
        br = self.login()
        waiting = []
        urgent = []
        for ticket in self.get_waiting_tickets(br):
            if ticket['urgent']:
                urgent.append(ticket['url'])
            else:
                waiting.append(ticket['url'])
        self.send_status(waiting, urgent)

    def login(self):
        br = Browser(self.starturl)
        br.getControl('Username:').value = self.acc_user
        br.getControl('Password:').value = self.acc_pass
        br.getControl('Login').click()
        return br

    def get_waiting_tickets(self, br):
        br.open(self.reporturl)
        base_url_tokens = urlparse(br.url)[:2]
        soup = BeautifulSoup(br.contents)
        for row in soup.find('table',
                             {'class': 'listing tickets'}).findAll('tr')[1:]:
            url = urlunparse(base_url_tokens + (row.a['href'], '', '', ''))
            br.open(url)
            ticket_soup = BeautifulSoup(br.contents)
            comments = ticket_soup.find('div', id='changelog')
            if not comments:
                who = ticket_soup.find('td', headers='h_reporter').text
                when = ticket_soup.find('a', {'class': 'timeline'})['title']\
                    .split('+')[0].strip()
            else:
                last_comment = comments.findAll('div',
                                                {'class': 'change'})[-1].h3
                who = 'by'.join(last_comment.text.split('by')[1:]).strip()
                when = last_comment.find('a', {'class': 'timeline'})['title']\
                    .split('+')[0].strip()

            when = datetime(*(strptime(when, '%Y-%m-%dT%H:%M:%S')[:7]))
            age = (datetime.utcnow() - when).days
            urgent = age > self.urgent
            if who not in self.ignore:
                yield {'url': url,
                       'urgent': urgent}

    def send_status(self, waiting, urgent):
        if not waiting and not urgent:
            return
        if urgent:
            if waiting:
                title = "There are %(urgent)s urgent and "
                "%(waiting)s normal tickets to answer"
            else:
                title = "There are %(urgent)s urgent tickets to answer"
        else:
            title = "There are %(waiting)s normal tickets to answer"
        title = title % {'urgent': len(urgent), 'waiting': len(waiting)}
        urgent = "\n".join(urgent)
        waiting = "\n".join(waiting)
        message = "From: %s\r\nTo: %s\r\nSubject: %s\r\n" % (self.from_,
                                                             self.to, title)
        if urgent:
            message += "There are urgent tickets:\n" + urgent + "\n\n"
        if waiting:
            message += "There are tickets waiting:\n" + waiting + "\n\n"

        server = smtplib.SMTP(self.mailhost, self.port)
        server.starttls()
        server.login(self.mail_user, self.mail_pass)
        server.sendmail(self.from_, [self.to], message)
        server.quit()


if __name__ == '__main__':
    Check()()
