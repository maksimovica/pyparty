#
# (C) Copyright 2013 George Washington University, D.C.
# All right reserved.
#
# This file is open source software distributed according to the terms in LICENSE.txt
from operator import attrgetter
import itertools
import logging
import copy

# 3rd Party Imports
import numpy as np
from enthought.traits.api import HasTraits, Instance, Property, Tuple,\
     cached_property, List

# Package Imports
from pyparty.shape_models.api import GROUPEDTYPES, ALLTYPES
from pyparty.shape_models.abstract_shape import Particle, ParticleError
from pyparty.config import NAMESEP, PADDING, ALIGN, MAXOUT
from pyparty.trait_types.metaparticle import MetaParticle

logger = logging.getLogger(__name__) 

def concat_particles(p1, p2, alternate=False, overwrite=False):
    """ Joins two instances of particle manager.
    
    Attributes
    ----------
    p1, p2 : ParticleManager
    
    alternate : Bool 
       Add particles in alternating order.  If False, all of p2 is added 
       after p1, meaning p2 would paint "over" p1 for particles w/ overlapping
       regions
       
    overwrite : Bool
       If True, particles in p2 with same name as those in p1 will overwrite.
       Otherwise, an error is raised if particles in p1 and p2 share names.
    
    Returns
    -------
    pout : ParticleManager
       Merged particle manager containing all particles of p1 and p2.
       
    Notes
    -----
    When overwriting, the elements are deleted from p1
    """
    p1_temp = copy.copy(p1)
    shared = [name for name in p1.names if name in p2.names]
    if shared:
        if overwrite:
            p1_temp.plist[:] = [p for p in p1 if p.name not in shared]
        else:
            raise ManagerError("%s Duplicate particle names found." % len(shared))
            
    pout = p1_temp.plist + p2.plist

    #http://stackoverflow.com/questions/7529376/pythonic-way-to-mix-two-lists    
    if alternate:
        pout = [p for pout in map(None, p1_temp, p2) for p in pout]
        pout = [p for p in pout if p is not None]
            
    return ParticleManager(plist=pout)

def subtract_particles(p1, p2):
    p1_temp = copy.copy(p1)
    shared = [name for name in p1.names if name in p2.names]    
    p1_temp.plist[:] = [p for p in p1 if p.name not in shared]
    return p1_temp            

def summarize_particles(obj):
    """ Return a summarized """
    if len(obj) == 0:
        countstring = '0 particles'
        ptypestring = ''
        
    elif len(obj) == 1:
        countstring = '1 particle (%s)' % obj[0].name
#        ptypestring = '%s type' % obj[0].ptype
    else:
        countstring = '%s particles (%s...%s)' % \
            (len(obj), obj[0].name, obj[-1].name)
 #       ptypestring = '%s ptypes' % len(obj.ptypes)
 
    if len(obj) > 1:
        if len(obj.ptypes) > 1:
            ptypestring = '%s ptypes' % len(obj.ptypes)
        ptypestring = ' ptype="%s"' % obj[0].ptype

    address = super(ParticleManager, obj).__repr__() .split()[-1].strip('>')      
    
    return ('\n<< %s /%s at %s >>' % 
            (countstring, ptypestring, address ) )    

def format_particles(obj, align='l', padding=3, header=True):
    """ Output column-delimted representation of a ParticleManager instance.

    Attributes
    ----------
    obj : ParticleManager
    
    maxlines : number of lines to print before cutting off.
    
    align : str ('l', 'c', 'r')
        Column alignment
    
    padding : int
        Column padding (width column = padding + len(max_word) )
    """
    padding = ' ' * padding
    just_fcn = {
        'l': str.ljust,
        'r': str.rjust,
        'c': str.center}[align]

    outlist = copy.copy(obj.plist)
    
    if header:
        outrows = [('', 'NAME', 'PTYPE')] 
    else:
        outrows = [('', '', '')]
        
    outrows.extend( [(str(i), p.name, p.ptype) for i, p in enumerate(outlist) ])
 
    widths = [max(map(len, col)) for col in zip(*outrows)]
    return  '\n'.join( [ padding.join((just_fcn(val,width) for val, width 
                    in zip(row, widths))) for row in outrows] )
        
class ManagerError(Exception):
    """ Particle Manager general Exception """
    
class KeyErrorManager(KeyError):
    """ Particle Manager dictionary interface Exception """   

        
        
class ParticleManager(HasTraits):
    """ Container class for creating, storing, managing particles;
        provides API used by higher-level objects.  Provides a property
        interface for easy mapping and slicing.  
    """
            
    plist = List(Instance(MetaParticle))
    _namemap = Property(Tuple, depends_on = 'plist')
   
    def __init__(self, fastnames=False, *traits, **traitkwds):
        """ fastnames:
           (TRUE):  circle_1, dimer_2, circle_3, dimer_4
           (FALSE): circle_1, dimer_1, circle_2, dimer_2
        """
        self.fastnames = fastnames
        super(ParticleManager, self).__init__(*traits, **traitkwds)
   
    @cached_property
    def _get__namemap(self):
        """ Store light map of name to index for faster name lookup.  I verified
            that this updates when plist elemnts are updated as well as obj itself.
            """
        return dict( (pobj.name, idx) for idx, pobj in enumerate(self.plist))    
            
    # ADD INDEX KEYWORD TO SUPPORT INSERTIONS
    def add(self, particle, name='', idx=None, color=None,
                      *traitargs, **traitkwargs):
        """ If color not passed, default color is used
            If not idx, put in last entry  """
    
        # Make particle from name and arguments
        if isinstance(particle, basestring):
            particle = self._make_particle(particle, *traitargs, **traitkwargs)

        if not idx:
            idx = len(self)
       
        #Generate key if it does not yet exist
        if not name:
            ptype = particle.ptype
            
            if self.fastnames:
                name = ptype + NAMESEP + str(idx)            
            
            else:
                try:
                    pcount = self.ptype_count[ptype]
                except KeyError:
                    pcount = 0
    
                name = ptype + NAMESEP + str(pcount)            

            
        if name in self._namemap:
            raise ManagerError('particle %s is already named "%s"' % 
                                 (self._namemap[name], name) )        
        if color:
            meta = MetaParticle(name=name, color=color, particle=particle)
        else:
            meta = MetaParticle(name=name, particle=particle)
        

        if idx == len(self):
            self.plist.append(meta)
        else:
            self.plist.insert(idx, meta)
                
    def _make_particle(self, ptype='', *traitargs, **traitkwargs):
        """ Instantiate a particle through string specifying class type
            via PARTICLETYPES """
        try:
            pclass = ALLTYPES[ptype]
        except KeyError:
            raise KeyErrorManager('"%s" is not an understood Particle type.  '
                'Choose from: %s' % (ptype, self.available()))
        return pclass(*traitargs, **traitkwargs)
    
    
    def map(self, fcn, *args, **kwargs):
        """ Apply a function to all particles.  Can also use functools.partial"""
        self.plist[:] = [fcn(p, *args, **kwargs) for p in self.plist]
        
    def reverse(self):
        """ In place since list is inplace """
        self.plist.reverse()
    
    def pop(self, idx):
        self.plist.pop(idx)
    
    def idx(self, *names):
        """ Return index given names """
        out = tuple(self._namemap[name] for name in names)
        if len(out) == 1:
            out = out[0]
        return out
    
    def _unmask_index(self, idx):
        """ Test if object is an integer, string, or isntance of 
            MetaParticle.  Returns index in any case. """

        if isinstance(idx, int) or isinstance(idx, slice):
            return idx

        if isinstance(idx, basestring):
            return self._namemap[idx]

        if isinstance(idx, MetaParticle):
            return self._namemap[idx.name]
        
        raise ManagerError("Index must be of type int, str or MetaParticle"
                           " received %s" % type(idx) )
        
    # Magic Methods
    # -------------
    def __add__(self, p2):
        return concat_particles(self, p2, alternate=False, overwrite=False)
    
    def __sub__(self, p2):
        """ Removes duplicates between p2, p1, but does not affect p1 particles
            otherwise."""
        return subtract_particles(self, p2)

    def __iter__(self):
        return self.plist.__iter__()
    
    def __getitem__(self, keyslice):
        """ Supports single name lookup; otherwise defers to list delitem"""

        if hasattr(keyslice, '__iter__'):
            # Boolean indexing
            if isinstance(keyslice, np.ndarray):
                boolout = keyslice.astype('bool')
                plout = [self.plist[idx] for idx, exists in enumerate(boolout) if exists]                
    
            else:    
                plout = [self.plist[self._unmask_index(idx)] for idx in keyslice]              

        else:
            plout = self.plist[self._unmask_index(keyslice)]

        # When slicing returns one value; still need to list-convert due to
        # trait type!
        if not hasattr(plout, '__iter__'):
            plout = [plout]
        
        return ParticleManager(plist=plout, fastnames=self.fastnames)

        
    def __delitem__(self, keyslice):
        """ Supports single name deletion; otherwise defers to list delitem.  
            Deletes in place to congruance with list API.
        
        Notes
        -----
        When deleting iteratively, avoid calls to "del" which changes size 
        during iteariton."""

        if hasattr(keyslice, '__iter__'):
            # Boolean indexing
            if isinstance(keyslice, np.ndarray):
                boolout = keyslice.astype('bool')
                self.plist[:] = [self.plist[idx] for idx, exists in
                                 enumerate(boolout) if not exists]
            else:    
                to_remove = [self._unmask_index(idx) for idx in keyslice]
                self.plist[:] = [self.plist[idx] for idx in range(len(self))
                                 if idx not in to_remove]

        # Delete single entry (can't del multiple as index changes inplace)
        else:
            del self.plist[self._unmask_index(keyslice)]
        

    def __setitem__(self, keyorslice, particle):
        """ Not sure how confident I am in implementing this.  Users can add, 
        and remove particles through add()/remove() (__get /__del) API.  
        Allowing them to set through slicing could break the API.  
        For example, setting many particles to the same value and hence the 
        same name...
        """
        raise ManagerError('"%s" object does not support item assigment.' % 
                           self.__class__.__name__)


    def __getattr__(self, attr):
        """ Return numpy array subset of self.plist based on attr. Attribute
            can be name, color, descriptor or otherwise common attribute of
            Particle class.  
            
            Notes
            -----
            Implemented similar pandas package to allow for attribute-based 
            indexing.
            
            Examples
            --------
            big_particles = p[p.perims > 50] """
        
        out = tuple(getattr(p, attr) for p in self.plist)
        return np.array(out)
    
    def __len__(self):
        return self.plist.__len__()
    
    # MAKE MORE SUCCINT
    def __repr__(self):
        """ <Particle at Address> [items]

        Examples
        --------
        <ParticleManager at 0x2c6eb30> [(circle_0 : circle ...],
        """        
        if len(self) >= MAXOUT or len(self) == 0:
            return summarize_particles(self)
        else:
            return format_particles(self, align=ALIGN, padding=PADDING)  
        
    def in_region(self, *coords):
        """ Get all particles whose CENTERS are within a rectangular region"""
        raise NotImplementedError
    

    # python properties
    # -------------
    @property
    def names(self):
        """ Particles names; so common, worth doing here"""
        return tuple(p.name for p in self.plist)
    
    @property
    def particles(self):
        """ Particle objects"""
        return tuple(p.particle for p in self.plist)
    
    @property
    def centers(self):
        """ Return center coordinates of all particles."""
        return tuple(p.center for p in self.plist)
    

    # Full attribute container sorted mappers        
    
    def sortby(self, attr='name', inplace=False):
        """ Sort list by attribute/descriptor"""

        plistout = sorted(self.plist, key=attrgetter(attr))

        if inplace:
            self.plist[:] = plistout
        else:
            return ParticleManager(plist=plistout)
        
    
    def _rr_cc_color(self):
        """ Returns rr_cc, color for each particle; useful to canvas """
        return [(p[3].rr_cc, p[2]) for p in self.plist]
    
    
    @property
    def ptypes(self):
        """ All UNIQUE particle types. """
        return tuple(set( p.ptype for p in self.plist ) )
        
    @property
    def ptype_count(self):
        """ Unique particle types in plist. """
        ptypes = tuple( p.ptype for p in self.plist) 
        return dict( (typ, ptypes.count(typ)) for typ in self.ptypes)
    
    def available(self, subtype=None):
        """ Show all valid particle types.  Subtype is 'simple' 'multi' to
            return groups of particles"""
        if subtype:
            return tuple( sorted(GROUPEDTYPES[subtype.lower()].keys()) )
        else:
            return tuple( (k+':', sorted(v.keys())) 
                          for k, v in GROUPEDTYPES.items() ) 
        
        
    # Class methods
    # ------------
    @classmethod
    def from_labels(cls, labelarray, prefix='label', colorbynum=False):
        """ Create ParticleManager from output of skimage.morphology.label
        array.  Each item is written to a general Particle type."""

        from pyparty.shape_models.io import LabeledParticle

        num = np.unique(labelarray)
        if num[0] == 0:
            num = num[1:]  #Will this ever not be the case?
        
        # Normalize color
        if colorbynum:
            color_norm = float(255)/max(num)       
       
        plist = []
        for idx, label in enumerate(num):
            name = '%s_%s' % (prefix, idx)
            rr_cc = np.where(labelarray==label)
            particle = LabeledParticle(rr_cc, label=label)
            
            if colorbynum:
                cn = color_norm * label      
                color = (0, 0, cn)
                plist.append( MetaParticle(name=name, color=color, 
                                           particle=particle) )
            else:
                plist.append( MetaParticle(name=name, particle=particle) )
      
        return cls(plist=plist)      
    
#http://stackoverflow.com/questions/9989334/create-nice-column-output-in-python               
        
if __name__ == '__main__':
    p=ParticleManager()
    for i in range(5):
        p.add(particle='circle', radius=i)
        p.add(particle='dimer')
        
    print 'starting'
    p2=ParticleManager()
    for i in range(50):
        p2.add(particle='circle', name='foo'+str(i), radius=i)
    print 'finished'
    
    print p[0:5]
    print p[0]
    
    
    #print len(p), p
    #print len(p2), p2
    #pout = concat_particles(p,p2, overwrite=False, alternate=False)    
    #print len(pout), pout
    
    #pminus = p2-p2
    #print len(pminus), pminus
    
    #print p
    #print ParticleManager()
    #print 'hi'


    #print p.name
    #print p.perimeter, type(p.perimeter), p.perimeter.dtype
    #print p[p.perimeter > 50]
    #print p.plist
    #del p[p.perimeter > 50]
    #print p.name