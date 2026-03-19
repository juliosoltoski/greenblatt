from django.urls import path

from apps.collaboration.views import (
    ActivityEventListView,
    CollectionDetailView,
    CollectionItemCreateView,
    CollectionItemDetailView,
    CollectionListCreateView,
    CommentDetailView,
    CommentListCreateView,
    SharedResourceView,
    ShareLinkDetailView,
    ShareLinkListCreateView,
)


urlpatterns = [
    path("comments/", CommentListCreateView.as_view(), name="collaboration-comment-list"),
    path("comments/<int:comment_id>/", CommentDetailView.as_view(), name="collaboration-comment-detail"),
    path("share-links/", ShareLinkListCreateView.as_view(), name="collaboration-share-link-list"),
    path("share-links/<int:share_link_id>/", ShareLinkDetailView.as_view(), name="collaboration-share-link-detail"),
    path("collections/", CollectionListCreateView.as_view(), name="collaboration-collection-list"),
    path("collections/<int:collection_id>/", CollectionDetailView.as_view(), name="collaboration-collection-detail"),
    path("collections/<int:collection_id>/items/", CollectionItemCreateView.as_view(), name="collaboration-collection-item-create"),
    path(
        "collections/<int:collection_id>/items/<int:item_id>/",
        CollectionItemDetailView.as_view(),
        name="collaboration-collection-item-detail",
    ),
    path("activity-events/", ActivityEventListView.as_view(), name="collaboration-activity-event-list"),
    path("shared/<str:token>/", SharedResourceView.as_view(), name="collaboration-shared-resource"),
]

