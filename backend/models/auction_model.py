"""
Flexy – Auction & Bid models (Supabase). Supports upcoming/active/ended status.
"""
import uuid
from datetime import datetime, timezone
from database import get_db

def create_auction(data, creator_id):
    ends_at = data['ends_at']
    if hasattr(ends_at, 'isoformat'): ends_at = ends_at.isoformat()
    auction = {
        'id':             str(uuid.uuid4()),
        'title':          data['title'],
        'description':    data.get('description',''),
        'category':       data.get('category','Other'),
        'image_url':      data.get('image_url',''),
        'starting_price': int(data['starting_price']),
        'reserve_price':  int(data.get('reserve_price',0)),
        'current_bid':    int(data['starting_price']),
        'current_bidder': None,
        'bid_count':      0, 'view_count': 0,
        'status':         'active',
        'created_by':     str(creator_id),
        'ends_at':        ends_at,
        'tags':           data.get('tags',[]),
        'is_featured':    False,
        'created_at':     datetime.now(timezone.utc).isoformat(),
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }
    resp = get_db().table('auctions').insert(auction).execute()
    return resp.data[0] if resp.data else auction

def get_auction(auction_id):
    try:
        r = get_db().table('auctions').select('*').eq('id', str(auction_id)).execute()
        return r.data[0] if r.data else None
    except Exception: return None

def list_auctions(status='active', category=None, sort='ends_at', limit=20, skip=0):
    q = get_db().table('auctions').select('*').eq('status', status)
    if category: q = q.eq('category', category)
    col, desc = {'bid_high':('current_bid',True),'newest':('created_at',True)}.get(sort,('ends_at',False))
    return q.order(col, desc=desc).range(skip, skip+limit-1).execute().data or []

def place_bid(auction_id, bidder_id, amount_paise):
    db = get_db()
    auction = get_auction(auction_id)
    if not auction: raise ValueError('Auction not found')
    if auction['status'] != 'active': raise ValueError('Auction is not active')

    ends_s = auction['ends_at']
    if ends_s.endswith('Z'): ends_s = ends_s[:-1]+'+00:00'
    ends_at = datetime.fromisoformat(ends_s)
    if ends_at.tzinfo is None: ends_at = ends_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > ends_at: raise ValueError('Auction has ended')
    if amount_paise <= auction['current_bid']: raise ValueError('Bid must exceed current bid')

    result = db.table('auctions').update({
        'current_bid':    amount_paise,
        'current_bidder': str(bidder_id),
        'bid_count':      auction['bid_count']+1,
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(auction_id)).eq('status','active').lt('current_bid', amount_paise).execute()

    if not result.data: raise ValueError('Bid race condition — someone placed a higher bid. Please refresh.')

    bid = {'id': str(uuid.uuid4()), 'auction_id': str(auction_id),
           'bidder_id': str(bidder_id), 'amount': amount_paise,
           'created_at': datetime.now(timezone.utc).isoformat()}
    db.table('bids').insert(bid).execute()
    return bid

def get_bid_history(auction_id, limit=20):
    r = get_db().table('bids').select('*').eq('auction_id', str(auction_id)).order('created_at', desc=True).limit(limit).execute()
    return r.data or []

def end_auction(auction_id):
    get_db().table('auctions').update({
        'status': 'ended', 'updated_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', str(auction_id)).execute()

def safe_auction(a):
    ends = a.get('ends_at','')
    if ends.endswith('Z'): ends = ends[:-1]+'+00:00'
    return {
        'id':             str(a['id']),
        'title':          a['title'],
        'description':    a.get('description',''),
        'category':       a.get('category',''),
        'image_url':      a.get('image_url',''),
        'starting_price': a['starting_price'],
        'reserve_price':  a.get('reserve_price',0),
        'current_bid':    a['current_bid'],
        'bid_count':      a.get('bid_count',0),
        'view_count':     a.get('view_count',0),
        'status':         a['status'],
        'created_by':     str(a['created_by']),
        'ends_at':        ends,
        'starts_at':      a.get('starts_at',''),
        'created_at':     a.get('created_at',''),
        'tags':           a.get('tags',[]),
        'is_featured':    a.get('is_featured',False),
        'order_id':       str(a['order_id']) if a.get('order_id') else None,
        'winner_id':      str(a['current_bidder']) if a.get('current_bidder') else None,
    }
