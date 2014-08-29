from collections import defaultdict
import traceback

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from WhatManager2.utils import get_user_token
from home.models import WhatTorrent, WhatFulltext, ReplicaSet, LogEntry
import WhatManager2.checks
from what_profile.models import WhatUserSnapshot


@permission_required('home.run_checks')
def checks(request):
    try:
        data = WhatManager2.checks.run_checks()
    except Exception:
        tb = traceback.format_exc()
        data = {
            'traceback': tb
        }
    return render(request, 'home/part_ui/checks.html', data)


@login_required
@permission_required('home.view_whattorrent')
def downloading(request):
    downloading = []
    for instance in ReplicaSet.get_what_master().transinstance_set.all():
        for m_torrent in instance.transtorrent_set.filter(torrent_done__lt=1):
            m_torrent.sync_t_torrent()
            downloading.append(m_torrent)
    downloading.sort(key=lambda t: t.torrent_date_added)
    data = {
        'torrents': downloading
    }
    return render(request, 'home/part_ui/downloading.html', data)


@login_required
@permission_required('home.view_whattorrent')
def recently_downloaded(request):
    count = 40
    recent = []
    for instance in ReplicaSet.get_what_master().transinstance_set.all():
        torrents = instance.transtorrent_set.filter(torrent_done=1)
        torrents = torrents.order_by('-torrent_date_added')[:count]
        recent.extend(torrents)
    recent.sort(key=lambda t: t.torrent_date_added, reverse=True)
    recent = recent[:count]

    for t in recent:
        t.playlist_name = 'what/{0}'.format(t.what_torrent_id)
    data = {
        'token': get_user_token(request.user),
        'torrents': recent,
    }
    return render(request, 'home/part_ui/recently_downloaded.html', data)


# Permission checks are inside function
@login_required
def recent_log(request):
    if request.user.has_perm('home.view_logentry'):
        types = request.POST['log_types'].split(',')
        entry_count = int(request.POST['count'])

        entries = LogEntry.objects.order_by('-datetime')
        entries = entries.filter(type__in=types)
        entries = entries[:entry_count]
        data = {
            'log_entries': entries
        }
    else:
        data = {
            'log_entries': [
                {
                    'type': 'info',
                    'message': 'You don\'t have permission to view logs.',
                }
            ]
        }
    return render(request, 'home/part_ui/recent_log.html', data)


@login_required
@permission_required('home.view_whattorrent')
def search_torrents(request):
    query = request.POST.get('query') or request.GET.get('query')
    query = ' '.join('+' + i for i in query.split())

    what_ids = WhatFulltext.objects.filter(info__search=query)
    what_ids = what_ids.extra(select={'score': 'MATCH(`info`) AGAINST (%s)'}, select_params=[query])
    what_ids = what_ids.extra(order_by=['-score'])
    what_ids = [w.id for w in what_ids]

    what_torrent_dict = WhatTorrent.objects.in_bulk(what_ids)
    what_torrents = [what_torrent_dict[i] for i in what_ids]

    for t in what_torrents:
        t.playlist_name = 'what/{0}'.format(t.id)

    data = {
        'token': get_user_token(request.user),
        'torrents': what_torrents,
    }
    return render(request, 'home/part_ui/search_torrents.html', data)


@login_required
@permission_required('home.view_whattorrent')
def error_torrents(request):
    error_torrents = []
    for instance in ReplicaSet.get_what_master().transinstance_set.all():
        error_torrents.extend(instance.transtorrent_set.exclude(torrent_error=0))
    data = {
        'torrents': error_torrents
    }
    return render(request, 'home/part_ui/error_torrents.html', data)


@login_required
def torrent_stats(request):
    what_buffer = 0
    try:
        what_buffer = WhatUserSnapshot.get_last().buffer_105
    except (WhatUserSnapshot.DoesNotExist, IndexError):
        pass
    data = {
        'master': ReplicaSet.get_what_master(),
        'buffer': what_buffer,
    }
    return render(request, 'home/part_ui/torrent_stats.html', data)


# Permission checks are inside template
@login_required
def stats(request):
    instance_stats = list()
    stats = defaultdict(lambda: 0)
    for instance in ReplicaSet.get_what_master().transinstance_set.all():
        istats = instance.client.session_stats()
        istats.instance_name = instance.name
        instance_stats.append(istats)

        stats['activeTorrentCount'] += istats.activeTorrentCount
        stats['totalUploadedBytes'] += istats.cumulative_stats['uploadedBytes']
        stats['totalDownloadedBytes'] += istats.cumulative_stats['downloadedBytes']
        stats['downloadedBytes'] += istats.current_stats['downloadedBytes']
        stats['uploadedBytes'] += istats.current_stats['uploadedBytes']
        stats['uploadSpeed'] += istats.uploadSpeed
        stats['downloadSpeed'] += istats.downloadSpeed
        stats['totalSecondsActive'] = max(stats['totalSecondsActive'],
                                          istats.cumulative_stats['secondsActive'])
        stats['secondsActive'] = max(stats['secondsActive'],
                                     istats.current_stats['secondsActive'])
    data = {
        'stats': stats,
        'instance_stats': instance_stats,
    }
    return render(request, 'home/part_ui/stats.html', data)
