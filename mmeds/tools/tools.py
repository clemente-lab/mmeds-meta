from time import sleep
from multiprocessing import Process

from mmeds.mmeds import send_email
from mmeds.authentication import get_email
from mmeds.error import AnalysisError
from mmeds.tools import Qiime1, Qiime2


def run_analysis(qiime):
    """ Run qiime analysis. """
    try:
        qiime.run()
    except AnalysisError as e:
        email = get_email(qiime.owner, testing=qiime.testing)
        send_email(email,
                   qiime.owner,
                   'error',
                   analysis_type=qiime.atype,
                   error=e.message,
                   testing=qiime.testing)


def test(time, atype):
    """ Simple function for analysis called during testing """
    sleep(time)


def spawn_analysis(atype, user, access_code, config, testing):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        qiime = Qiime1(user, access_code, atype, config, testing)
        p = Process(target=run_analysis, args=(qiime,))
    elif 'qiime2' in atype:
        qiime = Qiime2(user, access_code, atype, config, testing)
        p = Process(target=run_analysis, args=(qiime,))
    elif 'test' in atype:
        time = float(atype.split('-')[-1])
        p = Process(target=test, args=(time, atype))
    p.start()
    return p
