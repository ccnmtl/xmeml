import xml.dom.minidom as dom
from uuid import uuid1
from copy import deepcopy

#### TODO
# ...
# * splice transitionitems, too

###XML methods for stupid-XML structures like <clipitem> and <file>
def xmltextkey(domnode, key):
    "xmltextkey(domnode, 'foo') for <domnode><foo>bar</foo></domnode> will yield u'bar' "
    v = domnode.getElementsByTagName(key)
    if v.length:
        return v[0].firstChild.data
    else:
        return None

def xml2dict(domnode, go_deep=False, drop=tuple()):
    "only works for trees without attributes except @id which then drops children"
    if not go_deep and hasattr(domnode,'getAttribute') \
            and domnode.getAttribute('id'):
        return [ domnode.getAttribute('id') ]
    elif domnode.childNodes.length == 1 and domnode.firstChild.nodeType==3:
        return domnode.firstChild.data #textnode with data
    elif domnode.childNodes.length == 0:
        return None
    else: #tree
        #see bottom of file for KeyedArray
        return KeyedArray([( n.tagName, xml2dict(n, drop=drop) ) 
                     for n in domnode.childNodes 
                     if (n.nodeType==1 and n.tagName not in drop)])
    
def dict2xml(dic, doc, parentTag):
    "only works for trees without attributes except @id which then drops children"
    p = doc.createElement(parentTag)
    if isinstance(dic, list):
        p.setAttribute('id',dic[0]) 
    elif isinstance(dic, dict) or isinstance(dic,KeyedArray):
        for k,v in dic.items():
            if v is not None:
                p.appendChild(dict2xml(v, doc, k))
    else: #string or unicode
        p.appendChild(doc.createTextNode(unicode(dic)))
    return p


## XMEML objects

class Clip:
    """Not <clipitem> but a 'clip' of a section of a sequence.  
    This can be used to compose a new sequence from others
    """
    duration = 0
    def __init__(self, start_frame, end_frame, track_items, base_sequence):
        self.start_frame = int(start_frame)
        self.end_frame = int(end_frame)
        self.track_items = track_items
        self.sequence = base_sequence
        self.duration = (end_frame - start_frame)

    def lay_tracks(self, start=0):
        "returns track items with a <start/> corresponding to the argument "
        clip = {'start_frame':self.start_frame,'end_frame':self.end_frame}
        return [t.clip(clip,start) for t in self.track_items]


class Track:
    "<track> in <xmeml> represented as an object"
    def __init__(self,dom=None,source=None):
        self.clips = []

        if dom:
            self.dom = dom
            self.type = dom.parentNode.tagName #audio/video
            self.children = {
                'enabled':xmltextkey(dom, 'enabled'),
                'locked':xmltextkey(dom, 'locked'),
                'outputchannelindex':xmltextkey(dom, 'outputchannelindex'),
                }
        elif source:
            self.type = source.type
            self.children = deepcopy(source.children)
            self.source = source

class TrackItem:
    "<clipitem> or <transitionitem> object representation"
    def __init__(self, 
                 dom=None, 
                 source=None, inout=None, 
                 track=None
                 ):
        if source and inout and not dom:
            self.source = source
        elif dom:
            self.dom = dom
            self.parse(dom)
        else:
            raise Error('TrackItem init arguments must be [dom] xor [source, inout]')
        self.track = track

    def parse(self, dom):
        self.parsed = xml2dict(dom, go_deep=True)
        self.type = dom.tagName
        if self.type not in ('transitionitem','clipitem'):
            raise Error('track item only supports clipitem and transitionitem and not %s'
                        % self.type)
        self.id=(dom.getAttribute('id') or None) #only for clipitem
        self.start_frame = int(self.parsed['start'])
        self.end_frame = int(self.parsed['end'])
        if self.type=='clipitem':
            self.in_frame = int(self.parsed.get('in',-1))
            self.out_frame = int(self.parsed.get('out',-1))

    def intersects(self, clip):
        """whether TrackItem intersects with clip which is a dictionary
        containing two keys 'start_frame' and 'end_frame'
        """
        return ((self.end_frame >= clip['start_frame'] or self.end_frame == -1) \
                    and (self.start_frame <= clip['end_frame']))


    def splice_match(self, clip):
        """whether we should include this trackitem for clip
        we drop <transitionitem>s for now because we'd need
        to decide about how to handle cutting the transitionitem
        """
        return (self.type=='clipitem' and self.intersects(clip) )

    def clipitem_splice(self, source, clip):
        """Returns start and end point of the track to be within clip.  
        It assumes the <clipitem> is already within the clip
        (see TrackItem.intersects(clip) to test that)
        """
        start = source.start_frame if (source.start_frame>-1) else source.in_frame
        end = source.end_frame if (source.end_frame>-1) else source.out_frame
        return [ max(source.in_frame, 
                     source.in_frame+(clip['start_frame']-start)
                     ),
                 min(source.out_frame,
                     source.out_frame-(end - clip['end_frame'])
                     )
                 ]

    def clip(self, clip, start=0):
        ti = TrackItem(source=self, inout=clip)
        #TODO: a lot of this should be in the __init__
        ti.parsed = deepcopy(self.parsed)
        ti.start_frame = start
        ti.duration = clip['end_frame']-clip['start_frame']
        ti.end_frame = start+ti.duration
        ti.in_frame, ti.out_frame = self.clipitem_splice(self,clip)

        ti.type = self.type
        ti.track = Track(source=self.track)
        ti.id = self.id

        ti.parsed.update({
                'start':ti.start_frame,
                'end':ti.end_frame,
                'in':ti.in_frame,
                'out':ti.out_frame,
                'duration':ti.duration,
                })
        return ti
    
    def transitionitem_splice_movein(self, source, clip):
        "moves transitionitem into the clip space"
        #manipulates <start>, <end>
        pass

    def transitionitem_splice_compress(self, source, clip):
        "moves transitionitem into the clip space"
        #manipulates <start>, <end>
        pass

    def transitionitem_splice_recenter(self, source, clip):
        "moves transitionitem into the clip space"
        #manipulates <start>, <end>
        pass

class XmemlFileRef:
    """object representation of <file> in <xmeml>"""
    source = None
    def __init__(self, dom=None, ):
        if dom:
            self.dom = dom
            self.id = dom.getAttribute('id')
            self.source = 'dom'

            self.parsed = xml2dict(dom, go_deep=True)

            #redundant
            self.pathurl = xmltextkey(dom, 'pathurl')
            self.name = xmltextkey(dom, 'name')

class VideoSequence:
    dom = None
    #defaults
    timecode_zero = 0 
    rate = 29.97
    def __init__(self, file=None, xml_string=None, clip_list=None):
        if file:
            self.dom = dom.parse(file)
            self.parse(self.dom)
        elif xml_string:
            self.dom = dom.parseString(xml_string)
            self.parse(self.dom)
        elif clip_list:
            pass


    def frame(self,t,units):
        if units=='frames': return t
        elif units=='seconds': return round(self.rate * t)
        elif units=='timecode':
            parts = t.split(';')
            hms = parts[0].split(':')
            frames = 0 if len(parts)<2 else int(parts[1])
            u = 1
            for x in hms:
                frames += (hms.pop() * self.rate)
                u=u*60
            return frames-self.timecode_zero

    
    def toxml(self):
        if self.dom:
            return self.dom
        elif self.clip_list:
            self.dom, self.uuid = self.clips2dom(self.clip_list)
            return self.dom

    def clips2dom(self, clip_list):
        newuuid = unicode( uuid1() )
        impl = dom.getDOMImplementation()
        #setup document
        newdom = impl.createDocument(None, 'xmeml', None)
        newdom.documentElement.setAttribute('version','4')

        #base stupid stuff off of first clip
        seq_data = deepcopy(clip_list[0].sequence.parsed)
        del seq_data['duration']
        del seq_data['out']
        seq_data['in'] = 0

        seq = dict2xml(seq_data, newdom, 'sequence')
        newdom.documentElement.appendChild(seq)

        #lay tracks from each clip
        sections = {
            'audio': newdom.getElementsByTagName('audio')[0],
            'video': newdom.getElementsByTagName('video')[0],
            }
        tracks = {}
        frame_index = 0
        files = {}
        for clip in clip_list:
            #TODO: should we append these to self.track_items?
            track_items = clip.lay_tracks(start = frame_index)
            
            for ti in track_items:
                tr_dom = None

                #we key off track.source because that's what they shared
                if ti.track.source in tracks:
                    tr_dom = tracks[ti.track.source]
                else:
                    tr_dom = dict2xml(ti.track.children, newdom,'track')
                    tracks[ti.track.source] = tr_dom
                    sections[ti.track.type].appendChild(tr_dom)

                ti_dom = dict2xml(ti.parsed,newdom,'clipitem')
                tr_dom.appendChild(ti_dom)
                if ti.id: #also needs cross-file conflict avoidance
                    ti_dom.setAttribute('id',ti.id)
                file = ti_dom.getElementsByTagName('file')[0]
                fid = file.getAttribute('id')
                if fid not in files:
                    newfile = dict2xml(clip.sequence.source_files[fid].parsed,
                                       newdom,'file')
                    ti_dom.replaceChild(newfile, file)

                    #TODO: make sure cross-file ids don't conflict
                    newfile.setAttribute('id',fid)
                    files[fid] = (newfile, clip.sequence.source_files[fid])

            frame_index += clip.duration


        #except <uuid>,<duration> Should we do the same with <name>?
        seq.insertBefore(dict2xml(frame_index,newdom,'duration'), seq.firstChild)
        seq.insertBefore(dict2xml(frame_index,newdom,'out'), seq.firstChild)
        seq.insertBefore(dict2xml(newuuid,newdom,'uuid'), seq.firstChild)

        return (newdom, newuuid)
        

    def clip(self, beginning, ending, units):
        "units possibilities are 'seconds' and 'frames', and 'timecodes'"
        c = {'start_frame':self.frame(beginning, units),
             'end_frame':self.frame(ending, units),
             'base_sequence':self,
             'track_items':[],
             }

        c['track_items'] = []
        for t in self.track_items:
            if t.splice_match(c):
                c['track_items'].append(t)
        return Clip(**c)

    def parse(self, xmldom):
        """parses xml dom, to fill 
        self.track_points, self.track_markers, self.source_files
        """
        self.source_files = dict()

        self.tracks = []
        self.track_items = []
        seq = xmldom.getElementsByTagName('sequence')[0]
        self.uuid = xmltextkey(seq, 'uuid')
        self.parsed = xml2dict(seq, go_deep=True, 
                               drop=('track','uuid','duration'))

        rate = self.parsed['rate'] #double
        if rate['ntsc'] == 'TRUE':
            self.rate = (29.97/30) * float(rate['timebase'])
        else:
            self.rate = float(rate['timebase'])

        self.timecode_zero = int(self.parsed['timecode']['frame']) #double

        files = xmldom.getElementsByTagName('file')
        for f in files:
            if f.childNodes.length: #not just pointer
                id = f.getAttribute('id')
                self.source_files[id] = XmemlFileRef(dom=f)
                
        tracks = xmldom.getElementsByTagName('track')
        track_index = 0
        for t in tracks:
            my_track = Track(dom=t)
            self.tracks.append(my_track)
            for n in t.childNodes:
                if n.nodeType==1 and n.tagName in ('clipitem','transitionitem'):
                    self.track_items.append( TrackItem(dom=n, track=my_track) )

class KeyedArray:
  """A list which can also be set and got like a dictionary
  This might not be the most intuitive interface, but it was the easiest
  way to add multiple elements of the same tagname support to the XML methods
  """
  def __init__(self, dict=None):
    self.dic = {}
    self.key_array = []
    self.val_array = []
    if isinstance(dict,list):
        for k,v in dict: self[k]=v

  def __getitem__(self,k):
    return self.dic[k]
  def __setitem__(self,k,val):
    self.key_array.append(k)
    self.val_array.append(val)
    self.dic[k] = val
  def __delitem__(self,k):
    if self.has_key(k):
        i = self.key_array.index(k)
        self.key_array.pop(i)
        self.val_array.pop(i)
        del self.dic[k]

  def get(self,k,default):
      return (default if not (k in self.dic) else self[k])
  def has_key(self,k):
      return (k in self.dic)
  def values(self):
      return self.val_array
  def items(self):
      return [(self.key_array[i],self.val_array[i]) for i in range(len(self.key_array))]
  def update(self,dict):
    for k in dict.keys():
      val = dict[k]
      if k in self.dic:
        self.val_array[self.key_array.index(k)]=val
        self.dic[k] = val
      else:
        self.dic[k] = dict[k]


