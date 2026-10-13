import io
import json
import unittest
import zipfile

from app.management.models import AgentConfig
from app.management.contracts import resolve_input, render_prompt, validate_output
from app.management.connectors import import_skill


class ContractTests(unittest.TestCase):
    def test_manual_required_input_is_not_silently_omitted(self):
        config = AgentConfig(name='test',description='test',input_fields=[{'name':'category','required':True}]).model_dump()
        with self.assertRaisesRegex(ValueError,'输入校验'):
            resolve_input(config,{'query':'研究品类'})

    def test_input_sources_and_defaults_are_applied(self):
        config = AgentConfig(name='test',description='test',input_fields=[{'name':'question','source':'query','required':True},{'name':'files','source':'files','type':'array'},{'name':'limit','type':'number','default':3}]).model_dump()
        result = resolve_input(config,{'query':'问题'},files=['paper.pdf'])
        self.assertEqual(result['question'],'问题')
        self.assertEqual(result['files'],['paper.pdf'])
        self.assertEqual(result['limit'],3)

    def test_json_output_is_validated(self):
        config = AgentConfig(name='test',description='test',output_format='json').model_dump()
        self.assertEqual(validate_output(config,'{"answer":"yes"}'),{'answer':'yes'})
        with self.assertRaises(Exception):
            validate_output(config,'{"wrong":true}')

    def test_preview_does_not_expose_resource_secrets(self):
        config = AgentConfig(name='test',description='test',system_prompt='问题：{{query}}',knowledge=[{'resource_id':'kb','chat_ids':['chat']}]).model_dump()
        resources = {'kb':{'name':'内部白皮书','secret':'must-not-leak','discovery':{'chats':[{'id':'chat','name':'电商助手'}]}}}
        result = render_prompt(config,{'query':'品类策略'},resources)
        self.assertIn('品类策略',result)
        self.assertIn('电商助手',result)
        self.assertNotIn('must-not-leak',result)

    def test_skill_zip_preserves_supporting_files_and_rejects_traversal(self):
        content = '---\nname: analyst\ndescription: 分析资料\n---\n先阅读证据。'
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('analyst/SKILL.md',content)
            archive.writestr('analyst/references/example.md','示例内容')
        result = import_skill(data.getvalue(),'analyst.zip')
        self.assertEqual(result['config']['files']['references/example.md'],'示例内容')
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('../SKILL.md',content)
        with self.assertRaisesRegex(ValueError,'非法'):
            import_skill(data.getvalue(),'bad.zip')

    def test_invalid_skill_yaml_is_reported_as_configuration_error(self):
        with self.assertRaisesRegex(ValueError, 'YAML'):
            import_skill(b'---\nname: [broken\ndescription: bad\n---\ntext', 'SKILL.md')


if __name__ == '__main__':
    unittest.main()
