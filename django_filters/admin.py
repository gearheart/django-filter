from django.contrib import admin
from django.contrib.admin.views.main import IS_POPUP_VAR
from django.core.exceptions import PermissionDenied
from django.shortcuts import render_to_response
from django import template
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext

import django_filters
from django_filters.utils import AttributeCollector

class FilterModelAdmin(admin.ModelAdmin):
    def get_changelist_filterset(self, request):
        meta = type('Meta', (object,), {'model': self.model, 'fields': self.list_filter})
        return type('FilterSet', (django_filters.FilterSet,), {'Meta': meta})


    def changelist_view(self, request, extra_context=None):
        "The 'change list' admin view for this model."
        opts = self.model._meta
        app_label = opts.app_label
        if not self.has_change_permission(request, None):
            raise PermissionDenied

        # Check actions to see if any are available on this changelist
        actions = self.get_actions(request)

        # Remove action checkboxes if there aren't any actions available.
        list_display = list(self.list_display)
        if not actions:
            try:
                list_display.remove('action_checkbox')
            except ValueError:
                pass


        FilterSet = self.get_changelist_filterset(request)
        filterset = FilterSet(request.GET or None, queryset=self.queryset(request))

        cl = AttributeCollector(request=request, model=self.model,
            list_display=list_display, list_display_links=self.list_display_links,
            list_filter=self.list_filter, date_hierarchy=self.date_hierarchy,
            search_fields=self.search_fields, list_select_related=self.list_select_related,
            list_per_page=self.list_per_page, list_editable=self.list_editable,
            result_count=len(filterset.qs), full_result_count=self.queryset(request).count(),
            lookup_opts=self.model._meta, model_admin=self, order_field=(self.model._meta.pk.name, 'desc'),
            get_query_string=lambda *args, **kwargs: request.GET.urlencode(),
            result_list=filterset.qs
        )

        # If the request was POSTed, this might be a bulk action or a bulk edit.
        # Try to look up an action first, but if this isn't an action the POST
        # will fall through to the bulk edit check, below.
        if actions and request.method == 'POST':
            response = self.response_action(request, queryset=formset.qs)
            if response:
                return response

        # If we're allowing changelist editing, we need to construct a formset
        # for the changelist given all the fields to be edited. Then we'll
        # use the formset to validate/process POSTed data.
        formset = None

        # Handle POSTed bulk-edit data.
        if request.method == "POST" and self.list_editable:
            FormSet = self.get_changelist_formset(request)
            formset = cl.formset = FormSet(request.POST, request.FILES, queryset=filterset.qs)
            if formset.is_valid():
                changecount = 0
                for form in formset.forms:
                    if form.has_changed():
                        obj = self.save_form(request, form, change=True)
                        self.save_model(request, obj, form, change=True)
                        form.save_m2m()
                        change_msg = self.construct_change_message(request, form, None)
                        self.log_change(request, obj, change_msg)
                        changecount += 1

                if changecount:
                    if changecount == 1:
                        name = force_unicode(opts.verbose_name)
                    else:
                        name = force_unicode(opts.verbose_name_plural)
                    msg = ungettext("%(count)s %(name)s was changed successfully.",
                                    "%(count)s %(name)s were changed successfully.",
                                    changecount) % {'count': changecount,
                                                    'name': name,
                                                    'obj': force_unicode(obj)}
                    self.message_user(request, msg)

                return HttpResponseRedirect(request.get_full_path())

        # Handle GET -- construct a formset for display.
        elif self.list_editable:
            FormSet = self.get_changelist_formset(request)
            formset = cl.formset = FormSet(queryset=filterset.qs)

        # Build the list of media to be used by the formset.
        if formset:
            media = self.media + formset.media
        else:
            media = self.media

        # Build the action form and populate it with available actions.
        if actions:
            action_form = self.action_form(auto_id=None)
            action_form.fields['action'].choices = self.get_action_choices(request)
        else:
            action_form = None

        is_popup = IS_POPUP_VAR in request.GET
        title = (is_popup and ugettext('Select %s') % force_unicode(opts.verbose_name) or ugettext('Select %s to change') % force_unicode(opts.verbose_name))

        context = {
            'title': title,
            'is_popup': is_popup,
            'cl': cl,
            'filterset': filterset,
            'media': media,
            'has_add_permission': self.has_add_permission(request),
            'root_path': self.admin_site.root_path,
            'app_label': app_label,
            'action_form': action_form,
            'actions_on_top': self.actions_on_top,
            'actions_on_bottom': self.actions_on_bottom,
        }
        context.update(extra_context or {})
        context_instance = template.RequestContext(request, current_app=self.admin_site.name)
        return render_to_response(self.change_list_template or [
            'admin/%s/%s/filter_change_list.html' % (app_label, opts.object_name.lower()),
            'admin/%s/filter_change_list.html' % app_label,
            'admin/filter_change_list.html'
        ], context, context_instance=context_instance)
