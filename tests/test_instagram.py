import tempfile, unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from PIL import Image
import instagram as m

class TestAdapter(unittest.TestCase):
    def setUp(self):
        self.a={'id':'x','slug':'noticia-x','title':'Titular de prueba con acentos y puntuación. '*5,'subtitle':'Una bajada periodística. '*20,'category':'Actualidad','publishedAt':m.stamp()}
    def test_photo(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'photo.jpg'; m.render(self.a,p,Image.new('RGB',(400,800),'red'))
            with Image.open(p) as im: self.assertEqual((im.format,im.size),('JPEG',(1080,1350)))
            self.assertLess(p.stat().st_size,8*1024*1024)
    def test_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'fallback.jpg'; m.render(self.a,p)
            with Image.open(p) as im: self.assertEqual((im.format,im.size),('JPEG',(1080,1350)))
    def test_no_image(self): self.assertIsNone(m.choose_photo(self.a)[0])
    def test_sensitive(self):
        with patch.dict(m.CFG,{'sensitive_slugs':['noticia-x']}):
            with patch.object(m,'download_photo') as fetch:
                self.assertIsNone(m.choose_photo(self.a)[0]); fetch.assert_not_called()
    def test_caption(self):
        self.assertIn(m.CFG['notice'],m.caption(self.a,True)); self.assertNotIn(m.CFG['notice'],m.caption(self.a,False)); self.assertIn(m.article_url(self.a),m.caption(self.a,False))
    def test_dedupe(self):
        state={'start_at':(m.now()-timedelta(hours=1)).isoformat(),'posts':{'x':{'status':'published'}}}
        self.assertEqual(m.select([self.a],state,3),[])
    def test_selection(self):
        state={'start_at':(m.now()-timedelta(hours=1)).isoformat(),'posts':{}}
        self.assertEqual(m.select([self.a],state,3),[self.a]); self.assertEqual(m.select([self.a],state,0),[])
    def test_baseline(self):
        state={'start_at':(m.now()+timedelta(seconds=2)).isoformat(),'posts':{}}
        self.assertEqual(m.select([self.a],state,3),[])
    def test_cap(self):
        state={'start_at':(m.now()-timedelta(hours=1)).isoformat(),'posts':{str(i):{'attempt_at':m.stamp()} for i in range(60)}}
        self.assertEqual(m.select([self.a],state,3),[])
    def test_publish_state_before_api(self):
        p={'slug':'a','container':'123','status':'pending'}; state={'posts':{'a':p}}
        with patch.object(m,'persist') as save, patch.object(m,'api',side_effect=RuntimeError('red')):
            with patch.dict(m.os.environ,{'META_IG_ID':'1234'}):
                with self.assertRaises(RuntimeError): m.publish_container(state,p)
            self.assertEqual(p['status'],'publishing'); save.assert_called_once()
    def test_no_republish_uncertain(self):
        p={'slug':'a','container':'123','status':'publishing'}; state={'posts':{'a':p}}
        with patch.object(m,'api',return_value={'status_code':'FINISHED'}),patch.object(m,'publish_container') as send:
            m.recover(state); send.assert_not_called()
if __name__=='__main__': unittest.main()
