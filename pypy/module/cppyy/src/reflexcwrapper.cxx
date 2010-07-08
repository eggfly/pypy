#include "cppyy.h"
#include "reflexcwrapper.h"
#include <vector>
#include <iostream>


cppyy_typehandle_t cppyy_get_typehandle(const char* class_name) {
   return Reflex::Type::ByName(class_name).Id();
}


void* cppyy_allocate(cppyy_typehandle_t handle) {
    return Reflex::Type((Reflex::TypeName*)handle).Allocate();
}

void cppyy_deallocate(cppyy_typehandle_t handle, cppyy_object_t instance) {
    Reflex::Type((Reflex::TypeName*)handle).Deallocate(instance);
}

void cppyy_call_v(cppyy_typehandle_t handle, int method_index,
                  cppyy_object_t self, int numargs, void* args[]) {
    std::vector<void*> arguments(args, args+numargs);
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    if (self) {
        Reflex::Object o(t, self);
        m.Invoke(o, 0, arguments);
    } else {
        m.Invoke(0, arguments);
    }
}

long cppyy_call_l(cppyy_typehandle_t handle, int method_index,
                  cppyy_object_t self, int numargs, void* args[]) {
    long result;
    std::vector<void*> arguments(args, args+numargs);
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    if (self) {
        Reflex::Object o(t, self);
        m.Invoke(o, result, arguments);
    } else {
        m.Invoke(result, arguments);
    }
    return result;
}

double cppyy_call_d(cppyy_typehandle_t handle, int method_index,
                    cppyy_object_t self, int numargs, void* args[]) {
    double result;
    std::vector<void*> arguments(args, args+numargs);
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    if (self) {
        Reflex::Object o(t, self);
        m.Invoke(o, result, arguments);
    } else {
        m.Invoke(result, arguments);
    }
    return result;
}   

void cppyy_destruct(cppyy_typehandle_t handle, cppyy_object_t self) {
    Reflex::Type t((Reflex::TypeName*)handle);
    t.Destruct(self, true);
}

static cppyy_methptrgetter_t get_methptr_getter(Reflex::Member m)
{
  Reflex::PropertyList plist = m.Properties();
  if (plist.HasProperty("MethPtrGetter")) {
    Reflex::Any& value = plist.PropertyValue("MethPtrGetter");
    return (cppyy_methptrgetter_t)Reflex::any_cast<void*>(value);
  }
  else
    return 0;
}

cppyy_methptrgetter_t cppyy_get_methptr_getter(cppyy_typehandle_t handle, int method_index)
{
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    return get_methptr_getter(m);
}


int num_methods(cppyy_typehandle_t handle) {
    Reflex::Type t((Reflex::TypeName*)handle);
    for (int i = 0; i < (int)t.FunctionMemberSize(); i++) {
        Reflex::Member m = t.FunctionMemberAt(i);
        std::cout << i << " " << m.Name() << std::endl;
        std::cout << "    " << "Stubfunction:  " << (void*)m.Stubfunction() << std::endl;
        std::cout << "    " << "MethPtrGetter: " << (void*)get_methptr_getter(m) << std::endl;
        for (int j = 0; j < (int)m.FunctionParameterSize(); j++) {
            Reflex::Type at = m.TypeOf().FunctionParameterAt(j);
            std::cout << "    " << j << " " << at.Name() << std::endl;
        }
    }
    return t.FunctionMemberSize();
}

char* method_name(cppyy_typehandle_t handle, int method_index) {
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    std::string name = m.Name();
    char* name_char = (char*)malloc(name.size() + 1);
    strcpy(name_char, name.c_str());
    return name_char;
}

char* result_type_method(cppyy_typehandle_t handle, int method_index) {
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    Reflex::Type rt = m.TypeOf().ReturnType();
    std::string name = rt.Name(Reflex::FINAL|Reflex::SCOPED|Reflex::QUALIFIED);
    char* name_char = (char*)malloc(name.size() + 1);
    strcpy(name_char, name.c_str());
    return name_char;
}

int num_args_method(cppyy_typehandle_t handle, int method_index) {
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    return m.FunctionParameterSize();
}

char* arg_type_method(cppyy_typehandle_t handle, int method_index, int arg_index) {

    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    Reflex::Type at = m.TypeOf().FunctionParameterAt(arg_index);
    std::string name = at.Name(Reflex::FINAL|Reflex::SCOPED|Reflex::QUALIFIED);
    char* name_char = (char*)malloc(name.size() + 1);
    strcpy(name_char, name.c_str());
    return name_char;
}

int is_constructor(cppyy_typehandle_t handle, int method_index) {
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    return m.IsConstructor();
}

int is_static(cppyy_typehandle_t handle, int method_index) {
    Reflex::Type t((Reflex::TypeName*)handle);
    Reflex::Member m = t.FunctionMemberAt(method_index);
    return m.IsStatic();
}

int is_subtype(cppyy_typehandle_t h1, cppyy_typehandle_t h2) {
    if (h1 == h2)
        return 1;
    Reflex::Type t1((Reflex::TypeName*)h1);
    Reflex::Type t2((Reflex::TypeName*)h2);
    return (int)t2.HasBase(t1);
}

cppyy_typehandle_t dynamic_type(cppyy_typehandle_t handle, cppyy_object_t self) {
    Reflex::Type t((Reflex::TypeName*)handle);
    const Reflex::Object* obj = (const Reflex::Object*)self;
    return t.DynamicType((*obj)).Id();
}

void myfree(void* ptr) {
    free(ptr);
}
