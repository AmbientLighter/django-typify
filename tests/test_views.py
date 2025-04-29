from django_typify import views

def test_views1():
    source = """
class VirtualMachineViewSet(structure_views.ResourceViewSet):
    queryset = models.VirtualMachine.objects.all().order_by("name")

    def start(self, request, uuid=None):
        virtual_machine = self.get_object()
"""
    _, new_content = views.process_one_file(source)
    assert new_content == """
class VirtualMachineViewSet(structure_views.ResourceViewSet):
    queryset = models.VirtualMachine.objects.all().order_by("name")

    def start(self, request, uuid=None):
        virtual_machine: models.VirtualMachine = self.get_object()
"""